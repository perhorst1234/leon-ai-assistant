# Leon AI Assistant — Agent Assignment Gate

Status: implemented MVP  
Scope: local mock assignments only.

## What changed

- Dashboard task action now creates an `agent_assignment_proposal` instead of directly starting an agent run.
- Applying an assignment proposal may start only `runner_kind: local_mock`.
- The resulting mock `agent_run` still waits for review via the existing `/api/agent-runs/review` flow.

## Hard limits

Assignment proposals and apply paths do not allow:

- OpenAI/Codex calls;
- external API/tool calls;
- shell commands;
- file writes outside explicitly assigned project-local scopes;
- dependency installs;
- account connections;
- secret reads;
- GPU jobs.

Direct real runner support is intentionally rejected until a separate runtime/provider gate exists.

## Verified

- Proposal creation creates no agent run.
- Apply creates exactly one local mock run.
- Duplicate apply fails.
- Reject creates no run.
- Existing agent-run review still works.
- Audit hash-chain remains valid.
- Dashboard no longer uses `/api/agent-runs/mock` as the normal task action.
