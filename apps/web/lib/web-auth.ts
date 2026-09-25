import { createHmac, randomBytes, scrypt as scryptCallback, timingSafeEqual } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { readFile, writeFile, link, unlink } from 'node:fs/promises';
import { promisify } from 'node:util';

const scrypt = promisify(scryptCallback);
const COOKIE = 'leon_session';
const SESSION_SECONDS = 60 * 60 * 24 * 14;

export type WebAuthConfig = { file?: string; sessionSecret?: string; setupCode?: string };
type Account = { version: 1; salt: string; hash: string };

export function webAuthConfig(): WebAuthConfig {
  return {
    file: process.env.LEON_WEB_AUTH_FILE,
    sessionSecret: process.env.LEON_WEB_SESSION_SECRET,
    setupCode: process.env.LEON_WEB_SETUP_CODE,
  };
}

function validConfig(config: WebAuthConfig): config is Required<WebAuthConfig> {
  return Boolean(config.file?.startsWith('/') && config.sessionSecret && config.sessionSecret.length >= 32
    && config.setupCode && config.setupCode.length >= 24);
}

export function authConfigured(config: WebAuthConfig): boolean { return validConfig(config); }

export function sameOrigin(request: Request): boolean {
  const origin = request.headers.get('origin');
  if (!origin) return false;
  const internal = new URL(request.url).origin;
  const publicOrigin = process.env.LEON_WEB_PUBLIC_ORIGIN;
  let temporaryOrigin = process.env.LEON_WEB_TEMP_ORIGIN;
  if (process.env.LEON_WEB_TEMP_ORIGIN_FILE) {
    try { temporaryOrigin = readFileSync(process.env.LEON_WEB_TEMP_ORIGIN_FILE, 'utf8').trim(); }
    catch { temporaryOrigin = undefined; }
  }
  return origin === internal || Boolean(publicOrigin?.startsWith('https://') && origin === publicOrigin)
    || Boolean(temporaryOrigin && /^https:\/\/[a-z]+(?:-[a-z]+)*\.trycloudflare\.com$/.test(temporaryOrigin) && origin === temporaryOrigin);
}

export async function readAccount(config: WebAuthConfig): Promise<Account | null> {
  if (!validConfig(config)) return null;
  try {
    const raw = JSON.parse(await readFile(config.file, 'utf8')) as Partial<Account>;
    if (raw.version !== 1 || typeof raw.salt !== 'string' || typeof raw.hash !== 'string'
      || !/^[a-f0-9]{32}$/.test(raw.salt) || !/^[a-f0-9]{128}$/.test(raw.hash)) throw new Error('Invalid account');
    return raw as Account;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null;
    throw error;
  }
}

function equalSecret(actual: string, expected: string): boolean {
  const a = Buffer.from(actual); const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function register(config: WebAuthConfig, code: string, password: string): Promise<'ok' | 'exists' | 'invalid'> {
  if (!validConfig(config) || !equalSecret(code, config.setupCode) || password.length < 12 || password.length > 256) return 'invalid';
  const salt = Buffer.from(randomBytes(16)).toString('hex');
  const hash = Buffer.from(await scrypt(password, Buffer.from(salt, 'hex'), 64) as Uint8Array).toString('hex');
  const temporary = `${config.file}.${Buffer.from(randomBytes(8)).toString('hex')}.tmp`;
  try {
    await writeFile(temporary, JSON.stringify({ version: 1, salt, hash }) + '\n', { flag: 'wx', mode: 0o600 });
    try { await link(temporary, config.file); }
    catch (error) { if ((error as NodeJS.ErrnoException).code === 'EEXIST') return 'exists'; throw error; }
    return 'ok';
  } finally {
    await unlink(temporary).catch(() => undefined);
  }
}

export async function checkPassword(account: Account, password: string): Promise<boolean> {
  if (password.length > 256) return false;
  const hash = Buffer.from(await scrypt(password, Buffer.from(account.salt, 'hex'), 64) as Uint8Array).toString('hex');
  return equalSecret(hash, account.hash);
}

function signature(config: WebAuthConfig, account: Account, expiry: number): string {
  return createHmac('sha256', config.sessionSecret!).update(`v1:${expiry}:${account.hash}`).digest('base64url');
}

export function sessionCookie(config: WebAuthConfig, account: Account, secure = true): string {
  const expiry = Math.floor(Date.now() / 1000) + SESSION_SECONDS;
  return `${COOKIE}=${expiry}.${signature(config, account, expiry)}; HttpOnly;${secure ? ' Secure;' : ''} SameSite=Lax; Path=/; Max-Age=${SESSION_SECONDS}`;
}

export function clearedSessionCookie(secure = true): string {
  return `${COOKIE}=; HttpOnly;${secure ? ' Secure;' : ''} SameSite=Lax; Path=/; Max-Age=0`;
}

export async function hasSession(request: Request, config: WebAuthConfig): Promise<boolean> {
  if (!validConfig(config)) return false;
  const account = await readAccount(config);
  if (!account) return false;
  const value = request.headers.get('cookie')?.split(';').map(part => part.trim()).find(part => part.startsWith(`${COOKIE}=`))?.slice(COOKIE.length + 1);
  if (!value) return false;
  const match = /^(\d{10})\.([A-Za-z0-9_-]{43})$/.exec(value);
  if (!match) return false;
  const expiry = Number(match[1]);
  if (expiry <= Math.floor(Date.now() / 1000) || expiry > Math.floor(Date.now() / 1000) + SESSION_SECONDS) return false;
  return equalSecret(match[2], signature(config, account, expiry));
}
