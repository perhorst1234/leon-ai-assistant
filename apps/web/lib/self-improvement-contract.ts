export type SelfImprovementProfile = 'git_diff_check' | 'python_syntax';

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
  changed_code_executed: false;
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

function binding(value: unknown, expectedStatus: 'pending_approval' | 'approved'): SelfImprovementBinding {
  if (!value || typeof value !== 'object') throw new Error('Onverwachte reviewreactie; niets goedgekeurd.');
  const source = value as Record<string, unknown>;
  if (source.status !== expectedStatus || source.changed_code_executed !== false
      || typeof source.approval_id !== 'string' || !source.approval_id || source.approval_id.length > 128
      || typeof source.patch_digest !== 'string' || !/^[a-f0-9]{64}$/.test(source.patch_digest)) {
    throw new Error('Onveilige reviewreactie; niets goedgekeurd.');
  }
  return {
    status: expectedStatus, approval_id: source.approval_id, patch_digest: source.patch_digest,
    allowed_files: normalizedFiles(source.allowed_files), validation_profile: profile(source.validation_profile),
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
      || JSON.stringify(expected.allowed_files) !== JSON.stringify(actual.allowed_files)) {
    throw new Error('Approval hoort niet exact bij deze preview; review gestopt.');
  }
}

export function normalizeSelfImprovementRun(value: unknown): SelfImprovementRun {
  if (!value || typeof value !== 'object') throw new Error('Onbekende runuitkomst; er wordt niets als geslaagd aangenomen.');
  const source = value as Record<string, unknown>;
  if (source.changed_code_executed !== false || typeof source.patch_digest !== 'string' || !/^[a-f0-9]{64}$/.test(source.patch_digest)) {
    throw new Error('Onveilige runuitkomst; gewijzigde code is niet bevestigd als review-only.');
  }
  const validation = source.validation && typeof source.validation === 'object' ? source.validation as Record<string, unknown> : {};
  const diff = source.diff && typeof source.diff === 'object' ? source.diff as Record<string, unknown> : {};
  const rollback = source.rollback && typeof source.rollback === 'object' ? source.rollback as Record<string, unknown> : {};
  return {
    status: text(source.status, 80), patch_digest: source.patch_digest, allowed_files: normalizedFiles(source.allowed_files), changed_code_executed: false,
    validation: { profile: text(validation.profile, 80), passed: bool(validation.passed), error: text(validation.error, MAX_ERROR), phase: text(validation.phase, 80) || undefined },
    diff: { passed: bool(diff.passed), after_hash: text(diff.after_hash, 128) },
    rollback: { performed: bool(rollback.performed), error: text(rollback.error, MAX_ERROR) },
    temporary_repository_deleted: source.temporary_repository_deleted === true,
  };
}
