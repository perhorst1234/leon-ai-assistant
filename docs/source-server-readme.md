# Leon AI Assistant

Local-first implementation workspace for the Leon/Gaia personal AI assistant.

The current repository starts from the product plan in [docs/personal-ai-assistant-plan.md](docs/personal-ai-assistant-plan.md). The first implementation layer is a lightweight control-plane dashboard: project progress, phased backlog, approval queue, and safe API-key intake into a local ignored env file.

## Run the dashboard

```bash
./scripts/leon-dashboard
```

Then open:

```text
http://127.0.0.1:8765
```

Secrets submitted through the dashboard are written to `.env.local`, which is ignored by git. The API never returns secret values.

## Model choice

Leon does not send everything to the most expensive model. The first routing policy is in `config/model-routing.json`.

```bash
./scripts/leon-model-choice --task-type tool_making --complexity medium --risk medium
./scripts/leon-model-choice --task-type classification --complexity low --risk low
./scripts/leon-model-choice --task-type architecture --complexity high --risk high
```

## Rate-limit resume wrapper

For future local Codex runner jobs:

```bash
./scripts/leon-codex-resume-watch -- codex exec -m gpt-5.6-terra --json "continue the next Leon task"
```

This waits/retries on likely 429/quota/rate-limit failures. It cannot force this chat session itself to restart outside the platform.

## Tailscale access

Tailscale is installed on this machine. To expose the local dashboard to your tailnet:

```bash
./scripts/leon-dashboard-token
./scripts/leon-dashboard
./scripts/leon-tailscale-dashboard
```

Remote/Tailscale access requires `LEON_DASHBOARD_TOKEN`. The token is stored in `.env.local` and is not printed by default. To reveal it locally:

```bash
./scripts/leon-dashboard-token --show
```

Do not use public Funnel without a separate approval.

## Current engineering rule

Build in this order:

1. Control plane: status, approvals, env intake, task queue.
2. Decision layer and task model.
3. Agent runtime adapter.
4. Memory/graph.
5. MCP hub.
6. Night improvement system.
7. Local model/GPU routing.

External tools, MCP servers, payments, account connections, code execution sandboxes, and production-like automation require explicit approval before installation or activation.
