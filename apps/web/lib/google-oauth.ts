import { createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import { mkdir, writeFile, rename, lstat, realpath, unlink } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';

export const GOOGLE_SCOPES = ['https://www.googleapis.com/auth/calendar.events.readonly', 'https://www.googleapis.com/auth/gmail.metadata'];
export const OAUTH_COOKIE = 'leon_google_oauth';
type Config = { clientId: string; clientSecret: string; publicOrigin: string; sessionSecret: string; credentialsFile: string; repositoryRoot: string };
type State = { state: string; verifier: string; sessionHash: string; origin: string; expires: number };
export function googleOAuthConfig(request?: Request): Config {
  const config = { clientId: process.env.GOOGLE_CLIENT_ID || '', clientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
    publicOrigin: process.env.LEON_WEB_PUBLIC_ORIGIN || '', sessionSecret: process.env.LEON_WEB_SESSION_SECRET || '',
    credentialsFile: process.env.GOOGLE_CREDENTIALS_FILE || '', repositoryRoot: resolve(process.cwd(), '../..') };
  if (request) config.publicOrigin = selectOAuthOrigin(request, config.publicOrigin, temporaryGoogleOrigin());
  return config;
}
export function temporaryGoogleOrigin(): string {
  let origin = process.env.LEON_WEB_TEMP_ORIGIN || '';
  if (process.env.LEON_WEB_TEMP_ORIGIN_FILE) {
    try { origin = readFileSync(process.env.LEON_WEB_TEMP_ORIGIN_FILE, 'utf8').trim(); } catch { return ''; }
  }
  try {
    const url = new URL(origin);
    return url.protocol === 'https:' && url.hostname.endsWith('.trycloudflare.com') && !url.username && !url.password && url.pathname === '/' && !url.search && !url.hash ? url.origin : '';
  } catch { return ''; }
}
export function selectOAuthOrigin(request: Request, primary: string, temporary: string): string {
  const host = request.headers.get('host') || new URL(request.url).host;
  const forwardedHost = request.headers.get('x-forwarded-host');
  for (const origin of [primary, temporary].filter(Boolean)) {
    const allowed = new URL(origin);
    if (host === allowed.host || forwardedHost === allowed.host) return allowed.origin;
  }
  // A LAN-IP session cannot return to a public hostname. Move to the working
  // HTTPS origin and require its own Leon login before creating OAuth state.
  return temporary || primary;
}
function valid(config: Config) {
  const origin = new URL(config.publicOrigin);
  if (!config.clientId || !config.clientSecret || config.sessionSecret.length < 32 || origin.protocol !== 'https:'
    || origin.pathname !== '/' || origin.search || origin.hash || origin.username || origin.password
    || !config.credentialsFile.startsWith('/') || resolve(config.credentialsFile).startsWith(resolve(config.repositoryRoot) + '/')) throw new Error('Google OAuth configuration unavailable');
}
const digest = (text: string) => createHash('sha256').update(text).digest('hex');
function sign(config: Config, value: string) { return createHmac('sha256', config.sessionSecret).update(value).digest('base64url'); }
export function startGoogleOAuth(config: Config, sessionCookie: string, now = Date.now()) {
  valid(config);
  const state: State = { state: Buffer.from(randomBytes(32)).toString('base64url'), verifier: Buffer.from(randomBytes(48)).toString('base64url'), sessionHash: digest(sessionCookie), origin: new URL(config.publicOrigin).origin, expires: now + 600000 };
  const packed = Buffer.from(JSON.stringify(state)).toString('base64url');
  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  url.search = new URLSearchParams({ client_id: config.clientId, redirect_uri: new URL(config.publicOrigin).origin + '/api/google/oauth/callback', response_type: 'code', scope: GOOGLE_SCOPES.join(' '), access_type: 'offline', prompt: 'consent', include_granted_scopes: 'true', state: state.state, code_challenge: createHash('sha256').update(state.verifier).digest('base64url'), code_challenge_method: 'S256' }).toString();
  return { url: url.toString(), cookie: `${OAUTH_COOKIE}=${packed}.${sign(config, packed)}; HttpOnly; Secure; SameSite=Lax; Path=/api/google/oauth; Max-Age=600` };
}
export function validateOAuthState(config: Config, cookie: string, state: string, sessionCookie: string, now = Date.now()): State {
  valid(config);
  if (cookie.length > 2048 || state.length > 100) throw new Error('Invalid OAuth state');
  const [packed, supplied] = cookie.split('.');
  const expected = sign(config, packed || '');
  const a = Buffer.from(supplied || ''); const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) throw new Error('Invalid OAuth state');
  const parsed = JSON.parse(Buffer.from(packed, 'base64url').toString('utf8')) as State;
  if (parsed.expires <= now || parsed.state !== state || parsed.sessionHash !== digest(sessionCookie) || parsed.origin !== new URL(config.publicOrigin).origin || !/^[A-Za-z0-9_-]{64}$/.test(parsed.verifier)) throw new Error('Invalid OAuth state');
  return parsed;
}
export async function exchangeGoogleCode(config: Config, code: string, verifier: string, fetcher = fetch) {
  valid(config);
  if (!code || code.length > 4096) throw new Error('Invalid Google code');
  const response = await fetcher('https://oauth2.googleapis.com/token', { method: 'POST', redirect: 'error', signal: AbortSignal.timeout(20000), headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ client_id: config.clientId, client_secret: config.clientSecret, code, code_verifier: verifier, redirect_uri: new URL(config.publicOrigin).origin + '/api/google/oauth/callback', grant_type: 'authorization_code' }).toString() });
  const raw = await response.text();
  if (!response.ok || raw.length > 65536) throw new Error('Google authorization unavailable');
  const result = JSON.parse(raw) as { refresh_token?: string; scope?: string };
  if (typeof result.refresh_token !== 'string' || !result.refresh_token || result.refresh_token.length > 8192 || typeof result.scope !== 'string') throw new Error('Google offline authorization missing');
  const granted = result.scope.split(' ').filter(scope => GOOGLE_SCOPES.includes(scope));
  if (!granted.length) throw new Error('Google scopes missing');
  const target = resolve(config.credentialsFile);
  await mkdir(dirname(target), { recursive: true, mode: 0o700 });
  if (await realpath(dirname(target)) !== dirname(target)) throw new Error('Credential directory invalid');
  const existing = await lstat(target).catch(() => null);
  if (existing?.isSymbolicLink()) throw new Error('Credential path invalid');
  const temporary = target + '.' + Buffer.from(randomBytes(12)).toString('hex') + '.tmp';
  await writeFile(temporary, JSON.stringify({ refresh_token: result.refresh_token, client_id: config.clientId, client_secret: config.clientSecret, granted_scopes: granted }), { mode: 0o600, flag: 'wx' });
  try { await rename(temporary, target); } finally { await unlink(temporary).catch(() => {}); }
}
export function oauthCookieValue(request: Request): string { return request.headers.get('cookie')?.split(';').map(v => v.trim()).find(v => v.startsWith(OAUTH_COOKIE + '='))?.slice(OAUTH_COOKIE.length + 1) || ''; }
export const clearOAuthCookie = `${OAUTH_COOKIE}=; HttpOnly; Secure; SameSite=Lax; Path=/api/google/oauth; Max-Age=0`;
