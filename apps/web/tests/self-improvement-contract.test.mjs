import assert from 'node:assert/strict';
import test from 'node:test';
import {
  assertSameSelfImprovementBinding, buildSelfImprovementApprove, buildSelfImprovementDraft,
  buildSelfImprovementRun, normalizeSelfImprovementApproval, normalizeSelfImprovementPreview,
  normalizeSelfImprovementRun,
} from '../lib/self-improvement-contract.ts';

const digest = 'a'.repeat(64);
const previewPayload = {
  status: 'pending_approval', approval_id: 'approval-one', patch_digest: digest,
  allowed_files: ['a.py'], validation_profile: 'python_syntax',
  execution_mode: 'static_review_only', sandbox_config_fingerprint: 'c'.repeat(64), image_base_commit: '',
  changed_code_executed: false, restart_behavior: 'x'.repeat(9000),
};

test('self-improvement builders preserve exact patch and emit exact bodies', () => {
  const patch = 'diff --git a/a.py b/a.py\n';
  const draft = buildSelfImprovementDraft(patch, 'b.py, a.py, b.py', 'python_syntax');
  assert.deepEqual(draft, { patch, allowed_files: ['a.py', 'b.py'], validation_profile: 'python_syntax' });
  assert.deepEqual(buildSelfImprovementApprove('approval-one'), { approval_id: 'approval-one' });
  assert.deepEqual(buildSelfImprovementRun('approval-one', patch), { approval_id: 'approval-one', patch });
  assert.throws(() => buildSelfImprovementDraft('x'.repeat(48_001), 'a.py', 'python_syntax'));
});

test('self-improvement preview and approval are bounded, exact and review-only', () => {
  const preview = normalizeSelfImprovementPreview(previewPayload);
  assert.equal(preview.changed_code_executed, false);
  assert.equal(preview.restart_behavior.length, 4096);
  const approval = normalizeSelfImprovementApproval({ ...previewPayload, status: 'approved' });
  assert.doesNotThrow(() => assertSameSelfImprovementBinding(preview, approval));
  assert.throws(() => assertSameSelfImprovementBinding(preview, { ...approval, patch_digest: 'b'.repeat(64) }));
  assert.throws(() => assertSameSelfImprovementBinding(preview, { ...approval, sandbox_config_fingerprint: 'd'.repeat(64) }));
  assert.throws(() => normalizeSelfImprovementPreview({ ...previewPayload, changed_code_executed: true }));
  assert.throws(() => normalizeSelfImprovementPreview({ ...previewPayload, patch_digest: 'short' }));
  assert.throws(() => normalizeSelfImprovementPreview({ ...previewPayload, allowed_files: ['b.py', 'a.py'] }));
  assert.throws(() => normalizeSelfImprovementPreview({ ...previewPayload, execution_mode: 'podman_tests', image_base_commit: '' }));
  assert.throws(() => normalizeSelfImprovementPreview({ ...previewPayload, image_base_commit: 'a'.repeat(40) }));
  assert.throws(() => normalizeSelfImprovementPreview({ ...previewPayload, sandbox_config_fingerprint: 'short' }));
});

test('self-improvement run strictly distinguishes static and Podman execution', () => {
  assert.throws(() => normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], changed_code_executed: true }));
  const result = normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'static_review_only', changed_code_executed: false, validation: { error: 'x'.repeat(5000) }, diff: {}, rollback: {} });
  assert.equal(result.validation.error.length, 1024);
  assert.equal(result.changed_code_executed, false);
  assert.equal(result.sandbox, undefined);
  const podman = normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'podman_tests', changed_code_executed: true, validation: { passed: true }, diff: {}, rollback: {}, sandbox: { status: 'passed', tests_passed: true } });
  assert.deepEqual(podman.sandbox, { status: 'passed', tests_passed: true });
  assert.equal(podman.changed_code_executed, true);
  assert.throws(() => normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'podman_tests', changed_code_executed: false, validation: {}, diff: {}, rollback: {} }));
  assert.throws(() => normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'static_review_only', changed_code_executed: false, validation: {}, diff: {}, rollback: {}, sandbox: { status: 'passed', tests_passed: true } }));
  assert.throws(() => normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'podman_tests', changed_code_executed: false, validation: {}, diff: {}, rollback: {}, sandbox: { status: 'unknown', tests_passed: false } }));
  assert.throws(() => normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'podman_tests', changed_code_executed: true, validation: {}, diff: {}, rollback: {}, sandbox: { status: 'passed', tests_passed: false } }));
  assert.throws(() => normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'podman_tests', changed_code_executed: false, validation: {}, diff: {}, rollback: {}, sandbox: { status: 'timed_out', tests_passed: false } }));
  assert.throws(() => normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'static_review_only', changed_code_executed: true, validation: {}, diff: {}, rollback: {} }));
  assert.throws(() => normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'podman_tests', changed_code_executed: true, validation: { passed: true }, diff: {}, rollback: {}, sandbox: { status: 'failed', tests_passed: false } }));
  assert.throws(() => normalizeSelfImprovementRun({ status: 'failed', patch_digest: digest, allowed_files: ['a.py'], execution_mode: 'podman_tests', changed_code_executed: false, validation: { passed: false }, diff: {}, rollback: {}, sandbox: { status: 'sandbox_rejected', tests_passed: false } }));
});
