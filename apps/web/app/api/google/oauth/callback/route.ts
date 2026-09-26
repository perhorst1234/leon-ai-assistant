import { hasSession, webAuthConfig } from '@/lib/web-auth';
import { clearOAuthCookie, exchangeGoogleCode, googleOAuthConfig, oauthCookieValue, validateOAuthState } from '@/lib/google-oauth';
export async function GET(request: Request) {
  const config = googleOAuthConfig(request);
  let result = 'error';
  try {
    if (!await hasSession(request, webAuthConfig())) throw new Error('Missing Leon session');
    const url = new URL(request.url);
    const session = request.headers.get('cookie')?.split(';').map(v => v.trim()).find(v => v.startsWith('leon_session=')) || '';
    const state = validateOAuthState(config, oauthCookieValue(request), url.searchParams.get('state') || '', session);
    if (url.searchParams.has('error')) throw new Error('Google consent declined');
    await exchangeGoogleCode(config, url.searchParams.get('code') || '', state.verifier);
    result = 'connected';
  } catch { /* Never return authorization codes, credentials or Google errors. */ }
  return new Response(null, { status: 302, headers: { Location: `/?space=today&google=${result}`, 'Set-Cookie': clearOAuthCookie, 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer' } });
}
