import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeServerStatus } from '../lib/server-status-contract.ts';

test('server status keeps bounded public metrics and matching memory fields', () => {
  const disks = Array.from({ length: 10 }, (_, index) => ({ label: `disk-${index}`, total_bytes: 200, free_bytes: 100 }));
  const status = normalizeServerStatus({
    enabled: true, status: 'healthy', os: { system: 'Darwin', machine: 'arm64' },
    uptime: { value: 7200 }, load: { value: [0.1, 0.2, 0.3, 99] },
    memory: { total_bytes: 1024, available_bytes: 512, free_bytes: 1 }, disk: disks,
    process: { running: true }, health: { status: 'healthy' }, permission_check_id: 'check-1',
  });
  assert.equal(status.memory.available_bytes, 512);
  assert.equal('free_bytes' in status.memory, false);
  assert.deepEqual(status.load.value, [0.1, 0.2, 0.3]);
  assert.equal(status.disk.length, 8);
  assert.equal(status.os.system, 'Darwin');
  assert.equal(status.uptime.value, 7200);
});

test('malformed status degrades to unavailable without throwing', () => {
  const status = normalizeServerStatus({ disk: 'private/path', load: { value: ['bad'] }, memory: null });
  assert.equal(status.enabled, false);
  assert.equal(status.status, 'unavailable');
  assert.deepEqual(status.disk, []);
  assert.deepEqual(status.load.value, []);
});
