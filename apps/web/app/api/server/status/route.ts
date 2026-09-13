import { forwardLeon } from '@/lib/leon-proxy';
export const dynamic = 'force-dynamic';
export async function GET(request: Request) {
  const url = new URL(request.url); url.searchParams.set('resource', 'server-status');
  return forwardLeon(new Request(url, request), { url: process.env.LEON_BACKEND_URL, token: process.env.LEON_DASHBOARD_TOKEN });
}
