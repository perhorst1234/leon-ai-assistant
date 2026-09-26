import { authConfigured, checkPassword, clearedSessionCookie, hasSession, readAccount, register, sameOrigin, sessionCookie, webAuthConfig } from '../../../lib/web-auth.ts';

export const dynamic = 'force-dynamic';
const json = (data: unknown, status = 200, cookie?: string) => Response.json(data, {
  status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...(cookie ? { 'Set-Cookie': cookie } : {}) },
});
const attempts = new Map<string, { count: number; until: number }>();
function limited(action: string) {
  const now = Date.now();
  const old = attempts.get(action);
  const bucket = old && now < old.until ? old : { count: 0, until: now + 60_000 };
  bucket.count++;
  attempts.set(action, bucket);
  return bucket.count > (action === 'register' ? 10 : 20);
}

export async function GET(request: Request) {
  const config = webAuthConfig();
  if (!authConfigured(config)) return json({ error: 'Webauthenticatie is niet ingesteld.' }, 503);
  const account = await readAccount(config);
  return json({ registered: Boolean(account), authenticated: account ? await hasSession(request, config) : false });
}

export async function POST(request: Request) {
  const config = webAuthConfig();
  const form = request.headers.get('content-type')?.startsWith('application/x-www-form-urlencoded') === true;
  const respond = (data: unknown, status = 200, cookie?: string) => form
    ? new Response(null, { status: 303, headers: { Location: status === 200 ? '/?space=today' : '/?auth=invalid', 'Cache-Control': 'no-store', ...(cookie ? { 'Set-Cookie': cookie } : {}) } })
    : json(data, status, cookie);
  if (!authConfigured(config)) return respond({ error: 'Webauthenticatie is niet ingesteld.' }, 503);
  if (!sameOrigin(request)) return respond({ error: 'Ongeldige herkomst.' }, 403);
  if (!form && !request.headers.get('content-type')?.startsWith('application/json')) return respond({ error: 'JSON vereist.' }, 415);
  const body = await request.text();
  if (Buffer.byteLength(body) > 1024) return respond({ error: 'Verzoek te groot.' }, 413);
  let data: Record<string, unknown>;
  try { const fields = new URLSearchParams(body); if (form && new Set(fields.keys()).size !== Array.from(fields.keys()).length) throw new Error(); data = form ? Object.fromEntries(fields) : JSON.parse(body); if (!data || Array.isArray(data) || typeof data !== 'object') throw new Error(); }
  catch { return respond({ error: 'Ongeldige invoer.' }, 400); }
  const action = data.action;
  const secure = new URL(request.headers.get('origin') ?? request.url).protocol === 'https:';
  if (action === 'logout') return respond({ ok: true }, 200, clearedSessionCookie(secure));
  if (action !== 'register' && action !== 'login') return respond({ error: 'Onbekende actie.' }, 400);
  if (limited(action)) return respond({ error: 'Te veel pogingen. Wacht een minuut.' }, 429);
  const password = data.password;
  if (typeof password !== 'string') return respond({ error: 'Wachtwoord vereist.' }, 400);
  if (action === 'register') {
    if (form && data.confirm !== password) return respond({ error: 'De wachtwoorden komen niet overeen.' }, 400);
    if (typeof data.code !== 'string') return respond({ error: 'Instelcode vereist.' }, 400);
    if (await readAccount(config)) return respond({ error: 'Er bestaat al een account.' }, 409);
    const outcome = await register(config, data.code, password);
    if (outcome === 'exists') return respond({ error: 'Er bestaat al een account.' }, 409);
    if (outcome === 'invalid') return respond({ error: 'Controleer de instelcode en kies een wachtwoord van minimaal 12 tekens.' }, 400);
  }
  const account = await readAccount(config);
  if (!account || (action === 'login' && !await checkPassword(account, password))) return respond({ error: 'Wachtwoord onjuist.' }, 401);
  return respond({ ok: true }, 200, sessionCookie(config, account, secure));
}
