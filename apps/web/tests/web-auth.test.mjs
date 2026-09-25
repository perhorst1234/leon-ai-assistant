import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { checkPassword, hasSession, readAccount, register, sameOrigin, sessionCookie } from '../lib/web-auth.ts';
import { forwardLeon } from '../lib/leon-proxy.ts';

test('first registration is single use and password never stored in plaintext', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'leon-auth-'));
  const config = { file: join(dir, 'account.json'), sessionSecret: 'session-secret-at-least-thirty-two-characters', setupCode: 'one-time-code-at-least-24-characters' };
  try {
    assert.equal(await readAccount(config), null);
    assert.equal(await register(config, 'wrong-code', 'very-long-password'), 'invalid');
    assert.equal(await register(config, config.setupCode, 'short'), 'invalid');
    assert.equal(await register(config, config.setupCode, 'correct horse battery'), 'ok');
    assert.equal(await register(config, config.setupCode, 'another-very-long-password'), 'exists');
    const stored = await readFile(config.file, 'utf8');
    assert.doesNotMatch(stored, /correct horse battery|one-time-code/);
    const account = await readAccount(config);
    assert.equal(await checkPassword(account, 'wrong password'), false);
    assert.equal(await checkPassword(account, 'correct horse battery'), true);
    const cookie = sessionCookie(config, account).split(';')[0];
    assert.match(sessionCookie(config, account), /; Secure;/);
    assert.doesNotMatch(sessionCookie(config, account, false), /; Secure;/);
    const request = new Request('http://localhost:5173/api/leon?resource=jobs', { headers: { cookie } });
    assert.equal(await hasSession(request, config), true);
    const invalid = new Request(request.url, { headers: { cookie: cookie.slice(0, -1) + 'x' } });
    assert.equal(await hasSession(invalid, config), false);
    const expired = new Request(request.url, { headers: { cookie: `leon_session=1000000000.${cookie.split('.')[1]}` } });
    assert.equal(await hasSession(expired, config), false);
    const forwarded = await forwardLeon(request, { url: 'http://127.0.0.1:8765', token: 'backend-secret', webAuth: config }, async (_url, options) => {
      assert.equal(options.headers.Authorization, 'Bearer backend-secret');
      return Response.json({ ok: true });
    });
    assert.equal(forwarded.status, 200);
    const denied = await forwardLeon(new Request(request.url, { headers: { authorization: 'Bearer backend-secret' } }), { url: 'http://127.0.0.1:8765', token: 'backend-secret', webAuth: config }, async () => { throw new Error('Called'); });
    assert.equal(denied.status, 401);
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test('public HTTPS origin remains accepted behind an internal proxy port', () => {
  const previous = process.env.LEON_WEB_PUBLIC_ORIGIN;
  process.env.LEON_WEB_PUBLIC_ORIGIN = 'https://leon-ai-assistant.duckdns.org';
  try {
    const url = 'https://leon-ai-assistant.duckdns.org:8443/api/auth';
    assert.equal(sameOrigin(new Request(url, { headers: { origin: 'https://leon-ai-assistant.duckdns.org' } })), true);
    assert.equal(sameOrigin(new Request(url, { headers: { origin: 'https://evil.example' } })), false);
    assert.equal(sameOrigin(new Request(url)), false);
  } finally {
    if (previous === undefined) delete process.env.LEON_WEB_PUBLIC_ORIGIN;
    else process.env.LEON_WEB_PUBLIC_ORIGIN = previous;
  }
});
