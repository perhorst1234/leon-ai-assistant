# Web validation

Validated 2026-09-09 in the completion worktree. Browser acceptance passed against the temporary fixture and dev server, including reload, changed text, approval, polling, idempotent recovery, and job detail selection beyond the newest 100 jobs.

- `npm test`: 19 passed.
- `npx tsc --noEmit`: passed.
- `npm run lint`: 0 errors; five existing unused-value warnings remain in `apps/web/app/page.tsx`.
- `npm run build`: passed with the existing Vite config-loader warning.
- `npm audit --audit-level=high`: 0 vulnerabilities after the narrow `sharp` override.
- Security-linked versions: Next/eslint-config-next 16.3.4, React/RSC 19.2.8, vinext 1.0.0-beta.9, Vite 8.2.2, Cloudflare Vite plugin 1.54.6, Wrangler 4.130.0, `sharp` override 0.35.4.
