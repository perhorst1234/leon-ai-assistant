import { timingSafeEqual } from 'node:crypto';

type Config = { url?: string; token?: string };
const routes: Record<string, Partial<Record<string, string>>> = {
  jobs: { GET: '/api/work/jobs', POST: '/api/work/jobs' },
  control: { POST: '/api/work/control' },
  tasks: { GET: '/api/work/tasks', POST: '/api/tasks' },
  model: { POST: '/api/work/model' },
  'model-preview': { POST: '/api/work/model/preview' },
};
const json = (data: unknown, status = 200) => Response.json(data, {
  status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' },
});

export async function forwardLeon(request: Request, config: Config, fetcher: typeof fetch = fetch): Promise<Response> {
  if (!config.url || !config.token) return json({ error: 'Stel LEON_BACKEND_URL en LEON_DASHBOARD_TOKEN in op de webserver.' }, 503);
  let backend: URL;
  try { backend = new URL(config.url); } catch { return json({ error: 'Ongeldige backendconfiguratie.' }, 503); }
  // The bridge is local-server-only, not a client-configurable/open proxy.
  if (backend.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(backend.hostname)
      || backend.username || backend.password || backend.pathname !== '/' || backend.search || backend.hash) {
    return json({ error: 'De backend moet een lokaal HTTP-adres zijn.' }, 503);
  }
  const authorization = request.headers.get('authorization') ?? '';
  const supplied = Buffer.from(authorization);
  const expected = Buffer.from(`Bearer ${config.token}`);
  if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) {
    return json({ error: 'Verbind met je Leon-dashboardtoken, niet je OpenAI-sleutel.' }, 401);
  }
  const url = new URL(request.url);
  if (request.method === 'POST' && request.headers.get('origin') !== url.origin) {
    return json({ error: 'Cross-origin wijzigingen zijn geblokkeerd.' }, 403);
  }
  const resource = url.searchParams.get('resource') ?? '';
  const target = Object.hasOwn(routes, resource) ? routes[resource][request.method] : undefined;
  if (!target || [...url.searchParams.keys()].some(key => !['resource', 'id', 'request_id'].includes(key))
      || url.searchParams.getAll('resource').length !== 1 || url.searchParams.getAll('id').length > 1
      || url.searchParams.getAll('request_id').length > 1
      || (url.searchParams.has('id') && url.searchParams.has('request_id'))
      || ((url.searchParams.has('id') || url.searchParams.has('request_id')) && (resource !== 'jobs' || request.method !== 'GET'))) {
    return json({ error: 'Onbekende Leon-route.' }, 404);
  }
  let body: string | undefined;
  if (request.method === 'POST') {
    if (!request.headers.get('content-type')?.startsWith('application/json')) return json({ error: 'JSON vereist.' }, 415);
    body = await request.text();
    if (Buffer.byteLength(body) > 64000) return json({ error: 'Verzoek te groot.' }, 413);
    try {
      const parsed = JSON.parse(body);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error();
    } catch { return json({ error: 'Ongeldige JSON.' }, 400); }
  }
  const upstream = new URL(target, backend);
  if (url.searchParams.has('id')) upstream.searchParams.set('id', url.searchParams.get('id')!);
  if (url.searchParams.has('request_id')) upstream.searchParams.set('request_id', url.searchParams.get('request_id')!);
  try {
    const response = await fetcher(upstream, {
      method: request.method, body, redirect: 'error', signal: AbortSignal.timeout(10000),
      headers: { Authorization: authorization, 'Content-Type': 'application/json' },
    });
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error();
    return json(await response.json(), response.status);
  } catch { return json({ error: 'Leon-backend niet bereikbaar. Je taakstatus is niet bekend; er wordt geen succes aangenomen.' }, 502); }
}
