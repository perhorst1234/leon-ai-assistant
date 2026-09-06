# Leon AI Assistant — GPU, OpenAI, Codex, model routing and Tailscale plan

## Decisions added

1. Leon must remain local-first and should be ready for a coming NVIDIA GPU.
2. A Tesla M40/P40 is treated as a possible local inference accelerator, not as the core dependency.
3. OpenAI API/Codex is the primary cloud route for tool-making, coding, review and hard reasoning.
4. Model choice must be dynamic:
   - cheap route for clear repeatable tasks;
   - balanced route for normal tool-making/debugging;
   - premium route only for complex/high-risk/high-value work.
5. Rate-limit handling must queue/wait/resume local jobs rather than repeatedly failing.
6. Dashboard access via Tailscale is allowed as a P0 operator feature, but exposure still needs an explicit approval/action.

## Model routing policy

The first policy lives in `config/model-routing.json`.

Default routes:

| Route | Model | Use |
|---|---|---|
| cheap | `gpt-5.6-luna` | extraction, classification, simple summaries, clear repeatable tasks |
| balanced | `gpt-5.6-terra` | everyday coding, tool-making, debugging, docs, routine research |
| premium | `gpt-5.6-sol` | architecture, security review, hard debugging, high-value decisions |
| local_gpu | local model via validated backend | private/low-risk local tasks after GPU benchmark |

Rules:

- Do not send everything to Sol.
- Do not use local GPU for critical reasoning until benchmarked.
- Max/Ultra, large model downloads, GPU-heavy jobs and new providers require approval.
- Every model decision must log model, route, reason, risk and approximate cost class.

## OpenAI/Codex key handling

Dashboard env keys:

- `OPENAI_API_KEY` for app/runtime OpenAI calls.
- `CODEX_API_KEY` for single-run Codex automation only.

Security rule:

- Do not expose `OPENAI_API_KEY` or `CODEX_API_KEY` as global environment variables to untrusted scripts.
- Codex automation should receive `CODEX_API_KEY` only for the single `codex exec` invocation.
- The dashboard may store local secrets in `.env.local` for MVP, but long term this should move to a real local secret store.

## Rate-limit resume

Script:

```bash
./scripts/leon-codex-resume-watch -- codex exec -m gpt-5.6-terra --json "continue the next Leon task"
```

Behavior:

- runs the command;
- if output suggests rate limit/quota/429/retry-after, waits and retries;
- defaults to 15 minutes between retries;
- exits immediately for non-rate-limit failures.

Limit:

- This cannot force a ChatGPT/Codex chat session to restart outside the product.
- It is for local Leon/Codex runner jobs and future task queue workers.

## Tailscale dashboard access

Script:

```bash
./scripts/leon-dashboard-token
./scripts/leon-dashboard
./scripts/leon-tailscale-dashboard
```

Behavior:

- verifies the dashboard is running locally;
- runs `tailscale serve --bg 8765`;
- prints Tailscale serve status.

Security rules:

- Tailscale Serve is tailnet-only by default.
- Do not use Tailscale Funnel for public internet access without a separate approval.
- Remote/Tailscale access requires `LEON_DASHBOARD_TOKEN`.
- Add stronger per-user authentication before exposing sensitive controls beyond the trusted tailnet.

Current status:

- `tailscale serve status` showed the private tailnet hostname (replaced here by `https://leon.example.ts.net/`) proxying to `http://127.0.0.1:8765` on the original server.
- A historical local curl to that tailnet URL failed during TLS with `unrecognized name`; this is not a current-machine check.
- Next verification step: open the URL from another device in the same tailnet. If it fails there too, troubleshoot Tailscale HTTPS/cert handling before relying on remote access.

## GPU readiness

Current machine inventory found no NVIDIA GPU. When the new GPU is installed, run:

```bash
lspci | grep -i nvidia
nvidia-smi
./scripts/leon-model-choice --task-type classification --complexity low --risk low --privacy private --local-gpu-ready
```

First benchmark targets:

1. driver stability;
2. VRAM available;
3. small quantized local model;
4. tokens/sec on realistic Leon tasks;
5. fallback when local inference fails.
