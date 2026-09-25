# Leon AI Assistant — Agent Assignment Gate

Status: implemented
Scope: durable local Ollama text-only assignments, with `local_mock` retained for compatibility tests.

## What changed

- Dashboard task action now creates an `agent_assignment_proposal` instead of directly starting an agent run.
- The dashboard creates `runner_kind: local_ollama` proposals by default.
- Applying a proposal creates an `agent_run` plus an idempotent job in the existing durable work queue.
- The worker calls Ollama only through `127.0.0.1`, retries bounded local failures, and projects the result back into the agent run.
- The resulting `agent_run` waits for review via the existing `/api/agent-runs/review` flow.

## Hard limits

Assignment proposals and apply paths do not allow:

- external OpenAI/Codex calls;
- external API/tool calls;
- shell commands;
- file writes outside explicitly assigned project-local scopes;
- dependency installs;
- account connections;
- secret reads;
- model downloads or unbounded GPU jobs.

The local runner receives no tool surface. It can produce text from the redacted task packet, but cannot inspect or change the host.

## Verified

- Proposal creation creates no agent run.
- Apply creates exactly one local model run and one work job.
- A worker/service restart reconciles a completed work job back into its agent run.
- Loopback Ollama results record zero provider cost.
- Duplicate apply fails.
- Reject creates no run.
- Existing agent-run review still works.
- Audit hash-chain remains valid.
- Dashboard no longer uses `/api/agent-runs/mock` as the normal task action.
