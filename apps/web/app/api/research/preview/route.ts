import { forwardLeon } from '@/lib/leon-proxy';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  const url = new URL(request.url);
  url.searchParams.set('resource', 'research-preview');
  return forwardLeon(new Request(url, request), { url: process.env.LEON_BACKEND_URL, token: process.env.LEON_DASHBOARD_TOKEN });
}
