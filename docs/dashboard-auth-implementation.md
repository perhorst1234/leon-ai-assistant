# Leon AI Assistant — dashboard auth implementation

Status: implemented slice, in review.

## Purpose

The dashboard is exposed through Tailscale Serve, so remote access must not expose approvals, task controls, audit data or secret-status without authentication.

## Auth model

Dependency-free token auth:

- `LEON_DASHBOARD_AUTH_MODE=tailnet` by default.
- Localhost hosts (`127.0.0.1`, `localhost`, `::1`) remain accessible without login for local development.
- Non-local Host headers, including `*.ts.net`, require either:
  - `Authorization: Bearer <LEON_DASHBOARD_TOKEN>`, or
  - login via `/login`, which sets an HttpOnly cookie.

Modes:

| Mode | Behavior |
|---|---|
| `tailnet` | localhost open, remote Host requires token |
| `required` | all dashboard/API requests require token |
| `off` / `disabled` | auth disabled; only use locally |

## Token management

Generate token:

```bash
./scripts/leon-dashboard-token
```

Reveal locally:

```bash
./scripts/leon-dashboard-token --show
```

Rotate:

```bash
./scripts/leon-dashboard-token --rotate
```

The token is stored in `.env.local`, which is git-ignored. The default generate command does not print the token.

## Verification performed

Localhost without auth:

```bash
curl -fsS http://127.0.0.1:8765/api/state
```

Remote Host without auth:

```bash
curl -H 'Host: leon.example.ts.net' http://127.0.0.1:8765/api/state
```

Expected: `401`.

Remote Host with Bearer token:

```bash
token="$(./scripts/leon-dashboard-token --show)"
curl -H 'Host: leon.example.ts.net' -H "Authorization: Bearer ${token}" http://127.0.0.1:8765/api/state
unset token
```

Expected: `200`.

## Security limits

- This is a practical local MVP auth layer, not full multi-user auth.
- Token value is available to processes that can read `.env.local`.
- Before exposing beyond a trusted tailnet, add stronger auth, CSRF handling, session rotation and per-action authorization.
