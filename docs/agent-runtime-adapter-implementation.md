# Leon AI Assistant — Agent Runtime Adapter implementation

Status: implemented local slice.

## Purpose

Leon needs bounded, reviewable agent work before real OpenAI/Codex/LLM execution is connected. This slice adds the runtime contract without external calls.

## Implemented

- `agent_runs` SQLite table.
- Task packet generation.
- Dynamic model routing via `config/model-routing.json`.
- Local-only `MockAgentRunner`.
- Agent run start/completion audit events.
- Agent run review API.
- Accepted run review advances its parent task through valid lifecycle states to
  `review`, with bounded run provenance; task completion remains a separate
  explicit review action.
- Dashboard agent-runs panel.

## Runtime contract

An agent run stores:

- `task_id`
- `agent_role`
- `status`
- `task_type`
- `complexity`
- `risk`
- `privacy`
- `budget_mode`
- provider/route/model/reasoning effort
- route reason
- task packet JSON
- allowed actions
- forbidden actions
- result summary
- evidence JSON
- review status/note

## Safety constraints

The mock adapter explicitly forbids:

- raw secret reads;
- env writes;
- dependency installs;
- external account connections;
- shell command execution;
- file modification;
- external messages;
- payments;
- GPU-intensive jobs.

It performs no external API calls and no filesystem mutation beyond normal SQLite/audit persistence.

## Model routing behavior

Examples:

| Task | Route |
|---|---|
| low-risk classification | `cheap` / `gpt-5.6-luna` |
| tool-making/debugging | `balanced` / `gpt-5.6-terra` |
| architecture/high-complexity | `premium` / `gpt-5.6-sol` |

## Verification performed

- Direct tests:
  - mock run creates `waiting_for_review` run;
  - tool-making uses `gpt-5.6-terra`;
  - forbidden actions include secrets/install/shell;
  - audit hash-chain remains valid;
  - reviewed run becomes accepted.
- Live API:
  - `POST /api/agent-runs/mock`;
  - `POST /api/agent-runs/review`;
  - `GET /api/state` shows agent runs;
  - audit hash-chain valid.
- Lifecycle tests:
  - accepted runs advance `new`, `planned` and `active` tasks through canonical
    transitions to `review` in one transaction;
  - rejected or changes-requested runs leave parent status unchanged;
  - repeat review creates no state or audit change;
  - task `review → done` still requires explicit result and verification note;
  - copied evidence is capped at eight short type/summary records and oversized
    JSON is not parsed.

## Not done yet

- Real OpenAI/Codex execution.
- Runtime capability isolation beyond policy metadata.
- Long-running queue worker.
- Retry/rate-limit integration into the runtime loop.
- Per-agent file write scopes.
