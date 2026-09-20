export type SelfImprovementProfile = 'git_diff_check' | 'python_syntax';
export type SelfImprovementExecutionMode = 'static_review_only' | 'podman_tests';
export type SelfImprovementSandboxStatus = 'passed' | 'failed' | 'timed_out' | 'cleanup_failed' | 'sandbox_unavailable' | 'sandbox_rejected' | 'not_started';

export type SelfImprovementDraft = {
  patch: string;
  allowed_files: string[];
  validation_profile: SelfImprovementProfile;
};

export type SelfImprovementBinding = {
  status: string;
  approval_id: string;
  patch_digest: string;
  allowed_files: string[];
  validation_profile: SelfImprovementProfile;
  execution_mode: SelfImprovementExecutionMode;
  sandbox_config_fingerprint: string;
  image_base_commit: string;
  changed_code_executed: false;
};

export type SelfImprovementPreview = SelfImprovementBinding & { restart_behavior?: string };

export type SelfImprovementRun = {
  status: string;
  patch_digest: string;
  allowed_files: string[];
  validation: { profile: string; passed: boolean; error: string; phase?: string };
  diff: { passed: boolean; after_hash: string };
  rollback: { performed: boolean; error: string };
  temporary_repository_deleted: boolean;
  execution_mode: SelfImprovementExecutionMode;
  changed_code_executed: boolean;
  sandbox?: { status: SelfImprovementSandboxStatus; tests_passed: boolean };
};

export const MAX_UI_PATCH_BYTES = 48_000;
const MAX_TEXT = 4096;
const MAX_FILES = 32;
const MAX_ERROR = 1024;
const text = (value: unknown, max = MAX_TEXT) => typeof value === 'string' ? value.slice(0, max) : '';
const bool = (value: unknown) => value === true;

function normalizedFiles(value: unknown): string[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > MAX_FILES) throw new Error('Onverwachte bestandslijst.');
  const result = value.map(item => {
    if (typeof item !== 'string' || !item || item.length > 240) throw new Error('Onverwachte bestandslijst.');
    return item;
  });
  const sorted = [...result].sort();
  if (new Set(result).size !== result.length || result.some((item, index) => item !== sorted[index])) {
    throw new Error('Bestandslijst moet uniek en gesorteerd zijn.');
  }
  return result;
}

function profile(value: unknown): SelfImprovementProfile {
  if (value !== 'git_diff_check' && value !== 'python_syntax') throw new Error('Onverwacht validatieprofiel.');
  return value;
}

function executionMode(value: unknown): SelfImprovementExecutionMode {
  if (value !== 'static_review_only' && value !== 'podman_tests') throw new Error('Onverwachte uitvoeringsmodus.');
  return value;
}

function sandboxConfig(value: Record<string, unknown>, mode: SelfImprovementExecutionMode): { sandbox_config_fingerprint: string; image_base_commit: string } {
  if (!/^[a-f0-9]{64}$/.test(typeof value.sandbox_config_fingerprint === 'string' ? value.sandbox_config_fingerprint : '')) {
    throw new Error('Onveilige sandboxconfiguratie; niets goedgekeurd.');
  }
  const image_base_commit = typeof value.image_base_commit === 'string' ? value.image_base_commit : '';
  if ((mode === 'static_review_only' && image_base_commit !== '')
      || (mode === 'podman_tests' && !/^[a-f0-9]{40}$/.test(image_base_commit))) {
    throw new Error('Onveilige sandboxbinding; niets goedgekeurd.');
  }
  return { sandbox_config_fingerprint: value.sandbox_config_fingerprint as string, image_base_commit };
}

function binding(value: unknown, expectedStatus: 'pending_approval' | 'approved'): SelfImprovementBinding {
  if (!value || typeof value !== 'object') throw new Error('Onverwachte reviewreactie; niets goedgekeurd.');
  const source = value as Record<string, unknown>;
  if (source.status !== expectedStatus || source.changed_code_executed !== false
      || typeof source.approval_id !== 'string' || !source.approval_id || source.approval_id.length > 128
      || typeof source.patch_digest !== 'string' || !/^[a-f0-9]{64}$/.test(source.patch_digest)) {
    throw new Error('Onveilige reviewreactie; niets goedgekeurd.');
  }
  const execution_mode = executionMode(source.execution_mode);
  const sandbox = sandboxConfig(source, execution_mode);
  return {
    status: expectedStatus, approval_id: source.approval_id, patch_digest: source.patch_digest,
    allowed_files: normalizedFiles(source.allowed_files), validation_profile: profile(source.validation_profile),
    execution_mode, ...sandbox,
    changed_code_executed: false,
  };
}

export function buildSelfImprovementDraft(patch: string, filesText: string, validationProfile: SelfImprovementProfile): SelfImprovementDraft {
  const allowed_files = [...new Set(filesText.split(',').map(item => item.trim()).filter(Boolean))].sort();
  const bytes = new TextEncoder().encode(patch).length;
  if (!patch || bytes > MAX_UI_PATCH_BYTES || !allowed_files.length || allowed_files.length > MAX_FILES) {
    throw new Error('Vul een patch en maximaal 32 bestanden in; patch mag maximaal 48 KB zijn.');
  }
  return { patch, allowed_files, validation_profile: validationProfile };
}

export const buildSelfImprovementApprove = (approvalId: string) => ({ approval_id: approvalId });
export const buildSelfImprovementRun = (approvalId: string, exactPatch: string) => ({ approval_id: approvalId, patch: exactPatch });

export function normalizeSelfImprovementPreview(value: unknown): SelfImprovementPreview {
  const result = binding(value, 'pending_approval');
  const source = value as Record<string, unknown>;
  return { ...result, restart_behavior: text(source.restart_behavior, MAX_TEXT) || undefined };
}

export function normalizeSelfImprovementApproval(value: unknown): SelfImprovementBinding {
  return binding(value, 'approved');
}

export function assertSameSelfImprovementBinding(expected: SelfImprovementBinding, actual: SelfImprovementBinding): void {
  if (expected.approval_id !== actual.approval_id || expected.patch_digest !== actual.patch_digest
      || expected.validation_profile !== actual.validation_profile
      || expected.execution_mode !== actual.execution_mode
      || expected.sandbox_config_fingerprint !== actual.sandbox_config_fingerprint
      || expected.image_base_commit !== actual.image_base_commit
      || JSON.stringify(expected.allowed_files) !== JSON.stringify(actual.allowed_files)) {
    throw new Error('Approval hoort niet exact bij deze preview; review gestopt.');
  }
}

export function normalizeSelfImprovementRun(value: unknown): SelfImprovementRun {
  if (!value || typeof value !== 'object') throw new Error('Onbekende runuitkomst; er wordt niets als geslaagd aangenomen.');
  const source = value as Record<string, unknown>;
  if (typeof source.changed_code_executed !== 'boolean' || typeof source.patch_digest !== 'string' || !/^[a-f0-9]{64}$/.test(source.patch_digest)) {
    throw new Error('Onveilige runuitkomst; uitvoering is niet bevestigd.');
  }
  const mode = executionMode(source.execution_mode);
  const validation = source.validation && typeof source.validation === 'object' ? source.validation as Record<string, unknown> : {};
  const diff = source.diff && typeof source.diff === 'object' ? source.diff as Record<string, unknown> : {};
  const rollback = source.rollback && typeof source.rollback === 'object' ? source.rollback as Record<string, unknown> : {};
  const rawSandbox = source.sandbox;
  if (mode === 'static_review_only' && rawSandbox !== undefined) throw new Error('Onveilige runuitkomst; statische review heeft geen sandboxresultaat.');
  if (mode === 'podman_tests' && (!rawSandbox || typeof rawSandbox !== 'object')) throw new Error('Onveilige runuitkomst; sandboxresultaat ontbreekt.');
  const sandboxSource = rawSandbox as Record<string, unknown> | undefined;
  const sandboxStatus = sandboxSource?.status;
  if (sandboxSource && sandboxStatus !== 'passed' && sandboxStatus !== 'failed' && sandboxStatus !== 'timed_out'
      && sandboxStatus !== 'cleanup_failed' && sandboxStatus !== 'sandbox_unavailable' && sandboxStatus !== 'sandbox_rejected' && sandboxStatus !== 'not_started') {
    throw new Error('Onveilige runuitkomst; onbekende sandboxstatus.');
  }
  if (sandboxSource && typeof sandboxSource.tests_passed !== 'boolean') throw new Error('Onveilige runuitkomst; testresultaat ontbreekt.');
  if (mode === 'static_review_only' && source.changed_code_executed !== false) throw new Error('Onveilige runuitkomst; statische review mag geen code uitvoeren.');
  if (sandboxSource) {
    const executionStatuses: SelfImprovementSandboxStatus[] = ['passed', 'failed', 'timed_out', 'cleanup_failed'];
    const executionExpected = executionStatuses.includes(sandboxStatus as SelfImprovementSandboxStatus);
    if (source.changed_code_executed !== executionExpected
        || sandboxSource.tests_passed !== (sandboxStatus === 'passed')) {
      throw new Error('Onveilige runuitkomst; sandboxbewijs is tegenstrijdig.');
    }
  }
  const normalizedStatus = text(source.status, 80);
  const validationPassed = bool(validation.passed);
  if (mode === 'static_review_only' && !['review_required', 'failed'].includes(normalizedStatus)) {
    throw new Error('Onveilige runuitkomst; statische status is onbekend.');
  }
  if (mode === 'podman_tests' && sandboxSource) {
    const expectedStatus = validationPassed
      ? (sandboxStatus === 'passed' ? 'review_required' : sandboxStatus)
      : 'failed';
    if (normalizedStatus !== expectedStatus || (!validationPassed && sandboxStatus !== 'not_started')) {
      throw new Error('Onveilige runuitkomst; status past niet bij sandboxbewijs.');
    }
  }
  return {
    status: normalizedStatus, patch_digest: source.patch_digest, allowed_files: normalizedFiles(source.allowed_files), execution_mode: mode, changed_code_executed: source.changed_code_executed,
    validation: { profile: text(validation.profile, 80), passed: validationPassed, error: text(validation.error, MAX_ERROR), phase: text(validation.phase, 80) || undefined },
    diff: { passed: bool(diff.passed), after_hash: text(diff.after_hash, 128) },
    rollback: { performed: bool(rollback.performed), error: text(rollback.error, MAX_ERROR) },
    temporary_repository_deleted: source.temporary_repository_deleted === true,
    ...(sandboxSource ? { sandbox: { status: sandboxStatus as SelfImprovementSandboxStatus, tests_passed: sandboxSource.tests_passed as boolean } } : {}),
  };
}
