import assert from 'node:assert/strict';
import test from 'node:test';
import { readPending, recoverModel, submitModel, usdToMicrousd } from '../lib/model-submission.ts';

const id = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee';
const draft = { task_id: 'task-a', prompt: 'Hallo', max_output_tokens: 512, max_cost_microusd: 10000 };
function memory() {
  const data = new Map();
  return { data, getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) };
}

test('money parsing uses exact micro-USD without float rounding or NaN', () => {
  assert.equal(usdToMicrousd('0,01'), 10000);
  assert.equal(usdToMicrousd('0.000001'), 1);
  for (const bad of ['0', '-1', 'NaN', '1e-2', '1.000001', '0.0000001']) assert.throws(() => usdToMicrousd(bad));
});

test('missing approval or edits after review never send or write storage', async () => {
  const storage = memory();
  const forbidden = () => { assert.fail('Must not call backend'); };
  await assert.rejects(submitModel(draft, draft, false, storage, forbidden));
  for (const changed of [{ ...draft, prompt: 'Anders' }, { ...draft, task_id: 'task-b' }, { ...draft, max_cost_microusd: 20000 }]) {
    await assert.rejects(submitModel(changed, draft, true, storage, forbidden));
  }
  assert.equal(storage.data.size, 0);
});

test('storage failure prevents sending', async () => {
  const storage = { ...memory(), setItem: () => { throw new Error('Storage unavailable'); } };
  await assert.rejects(submitModel(draft, draft, true, storage, () => assert.fail(), () => id));
});

test('uncertain request keeps only UUID, retry uses same id and then clears it', async () => {
  const storage = memory();
  await assert.rejects(submitModel(draft, draft, true, storage, async () => { throw new Error('Disconnected'); }, () => id));
  assert.equal(readPending(storage), id);
  assert.deepEqual([...storage.data.values()], [id]);
  const result = await submitModel(draft, draft, true, storage, async (resource, body) => {
    assert.equal(resource, 'model');
    assert.deepEqual(body, { ...draft, request_id: id, approve_external_text: true });
    return { job: { id: 'work-a', request_id: id } };
  }, () => assert.fail('Must not allocate another id'));
  assert.equal(result.id, 'work-a');
  assert.equal(readPending(storage), null);
});

test('reload recovery only queries the saved UUID and never repeats the POST', async () => {
  const storage = memory();
  await assert.rejects(submitModel(draft, draft, true, storage, async () => { throw new Error(); }, () => id));
  const recovered = await recoverModel(storage, async (resource, body, requestId) => {
    assert.equal(resource, 'jobs'); assert.equal(body, undefined); assert.equal(requestId, id);
    return { job: { id: 'work-a', request_id: id } };
  });
  assert.equal(recovered.id, 'work-a'); assert.equal(readPending(storage), null);
});

test('missing job or mismatched receipt never clears uncertainty', async () => {
  const storage = memory();
  await assert.rejects(submitModel(draft, draft, true, storage, async () => ({ job: { id: 'wrong', request_id: 'other' } }), () => id));
  assert.equal(await recoverModel(storage, async () => ({ job: null })), null);
  assert.equal(readPending(storage), id);
});
