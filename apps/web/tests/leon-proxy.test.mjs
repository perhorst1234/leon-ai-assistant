import assert from 'node:assert/strict';
import test from 'node:test';
import { forwardLeon } from '../lib/leon-proxy.ts';

const config = { url: 'http://127.0.0.1:8765', token: 'test-only-dashboard-token' };
const request = (resource = 'jobs', options = {}) => new Request(`http://localhost:5173/api/leon?resource=${resource}`, {
  ...options,
  headers: { authorization: `Bearer ${config.token}`, origin: 'http://localhost:5173', 'content-type': 'application/json', ...options.headers },
});
const forbiddenFetch = () => { throw new Error('Must not call backend'); };

test('missing configuration and missing authentication fail closed', async () => {
  assert.equal((await forwardLeon(request(), {}, forbiddenFetch)).status, 503);
  assert.equal((await forwardLeon(request('jobs', { headers: { authorization: '' } }), config, forbiddenFetch)).status, 401);
  assert.equal((await forwardLeon(request('jobs', { headers: { authorization: 'Bearer wrong' } }), config, forbiddenFetch)).status, 401);
});

test('bridge rejects remote destinations and credential-bearing URLs', async () => {
  for (const url of ['https://example.com', 'http://127.0.0.1.evil.invalid', 'http://user:pass@localhost:8765', 'http://localhost/private', 'http://localhost/?url=other']) {
    assert.equal((await forwardLeon(request(), { ...config, url }, forbiddenFetch)).status, 503);
  }
});

test('cross-origin or absent-origin writes never reach the backend', async () => {
  for (const origin of ['https://evil.invalid', 'null', '']) {
    assert.equal((await forwardLeon(request('jobs', { method: 'POST', body: '{}', headers: { origin } }), config, forbiddenFetch)).status, 403);
  }
});

test('only the explicit work/task routes and query shape are accepted', async () => {
  for (const resource of ['secrets', '../../secrets', '__proto__', 'constructor', 'jobs&id=a&id=b', 'tasks&id=a', 'jobs&url=https://evil.invalid', 'jobs&resource=control']) {
    assert.equal((await forwardLeon(request(resource), config, forbiddenFetch)).status, 404);
  }
});

test('oversized and malformed request bodies are rejected', async () => {
  assert.equal((await forwardLeon(request('jobs', { method: 'POST', body: 'x'.repeat(64001) }), config, forbiddenFetch)).status, 413);
  for (const body of ['no json', 'null', '[]']) assert.equal((await forwardLeon(request('jobs', { method: 'POST', body }), config, forbiddenFetch)).status, 400);
});

test('valid request forwards auth, preserves backend status, and never caches', async () => {
  let calls = 0;
  const response = await forwardLeon(request('jobs&id=work-one'), config, async (url, options) => {
    calls++;
    assert.equal(String(url), 'http://127.0.0.1:8765/api/work/jobs?id=work-one');
    assert.equal(options.headers.Authorization, `Bearer ${config.token}`);
    assert.equal(options.redirect, 'error');
    return Response.json({ error: 'Unknown work job' }, { status: 400 });
  });
  assert.equal(calls, 1);
  assert.equal(response.status, 400);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.deepEqual(await response.json(), { error: 'Unknown work job' });
});

test('backend outage and invalid response never become successful work', async () => {
  for (const fetcher of [async () => { throw new Error('private connection details'); }, async () => new Response('<html>bad gateway</html>')]) {
    const response = await forwardLeon(request(), config, fetcher);
    assert.equal(response.status, 502);
    assert.doesNotMatch(await response.text(), /private connection details/);
  }
});
