import assert from 'node:assert/strict';
import test from 'node:test';
import { approveReconciliation } from '../lib/model-reconciliation.ts';

const proposal = { job_id: 'work-a', receipt_sha256: 'a'.repeat(64), retry_allowed: false, task_completed: false };
test('cost recovery binds explicit approval to the selected job and receipt', async () => {
  for (const [id, quote, approved] of [['work-b', proposal, true], ['work-a', proposal, false],
    ['work-a', { ...proposal, retry_allowed: true }, true], ['work-a', { ...proposal, receipt_sha256: '' }, true]]) {
    await assert.rejects(approveReconciliation(id, quote, approved, () => assert.fail('No request')));
  }
  await approveReconciliation('work-a', proposal, true, async (resource, body) => {
    assert.equal(resource, 'reconciliation');
    assert.deepEqual(body, { id: 'work-a', receipt_sha256: proposal.receipt_sha256, approve_cost_reconciliation: true });
    return { job: { id: 'work-a', model_state: 'reconciled' } };
  });
});
test('cost recovery never treats another job or unconfirmed response as success', async () => {
  for (const response of [{}, { job: { id: 'work-b', model_state: 'reconciled' } }, { job: { id: 'work-a', model_state: 'unknown' } }]) {
    await assert.rejects(approveReconciliation('work-a', proposal, true, async () => response));
  }
});
