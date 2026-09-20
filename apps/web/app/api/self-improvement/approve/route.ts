import { forwardLeon } from '@/lib/leon-proxy';
export const dynamic = 'force-dynamic';
export async function POST(request: Request) {
  const url = new URL(request.url); return forwardLeon(new Request(`${url.origin}/api/self-improvement/approve?resource=self-improvement-approve`, request), { url: process.env.LEON_BACKEND_URL, token: process.env.LEON_DASHBOARD_TOKEN });
}
