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
  assert.throws(() => normalizeSelfImprovementPreview({ ...previewPayload, changed_code_executed: true }));
  assert.throws(() => normalizeSelfImprovementPreview({ ...previewPayload, patch_digest: 'short' }));
  assert.throws(() => normalizeSelfImprovementPreview({ ...previewPayload, allowed_files: ['b.py', 'a.py'] }));
});

test('self-improvement run rejects unknown execution semantics and bounds errors', () => {
  assert.throws(() => normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], changed_code_executed: true }));
  const result = normalizeSelfImprovementRun({ status: 'review_required', patch_digest: digest, allowed_files: ['a.py'], changed_code_executed: false, validation: { error: 'x'.repeat(5000) }, diff: {}, rollback: {} });
  assert.equal(result.validation.error.length, 1024);
  assert.equal(result.changed_code_executed, false);
});
