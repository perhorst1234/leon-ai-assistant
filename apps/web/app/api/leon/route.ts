import { forwardLeon } from '@/lib/leon-proxy';

export const dynamic = 'force-dynamic';

function handle(request: Request) {
  return forwardLeon(request, {
    url: process.env.LEON_BACKEND_URL,
    token: process.env.LEON_DASHBOARD_TOKEN,
  });
}

export const GET = handle;
export const POST = handle;
