import { hasSession, webAuthConfig } from '@/lib/web-auth';
import { googleOAuthConfig, startGoogleOAuth } from '@/lib/google-oauth';
export async function GET(request: Request) {
  try {
    const config = googleOAuthConfig(request);
    const host = request.headers.get('host') || new URL(request.url).host;
    const forwardedHost = request.headers.get('x-forwarded-host');
    const destination = new URL(config.publicOrigin);
    if (host !== destination.host && forwardedHost !== destination.host || !await hasSession(request, webAuthConfig())) {
      return new Response(null, { status: 302, headers: { Location: `${destination.origin}/?space=today`, 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer' } });
    }
    const result = startGoogleOAuth(config, request.headers.get('cookie')?.split(';').map(v => v.trim()).find(v => v.startsWith('leon_session=')) || '');
    return new Response(null, { status: 302, headers: { Location: result.url, 'Set-Cookie': result.cookie, 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer' } });
  } catch { return Response.json({ error: 'Google is nog niet configureerbaar. Controleer de serverinstellingen.' }, { status: 503 }); }
}
