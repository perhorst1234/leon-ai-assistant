# Leon AI Assistant — Orchestration Proposal layer

Status: implemented MVP  
Scope: local review proposals only; no execution.

## What this slice adds

- `src/leon_control_plane/orchestrator.py`
  - Converts a `routing_decision` into a reviewable orchestration proposal.
  - Proposals explicitly set:
    - `execution_allowed: false`
    - `external_calls_made: false`
    - `secret_values_read: false`
  - Direct/refusal routes never propose executable work.
  - Research/queue routes propose bounded local tasks.
  - Approval-required routes propose a local task plus a pending approval card.

- SQLite persistence
  - Adds `orchestration_proposals`.
  - Proposal creation is audited as `orchestration_proposed`.
  - Proposal apply is audited as `orchestration_applied`.
  - Proposal rejection is audited as `orchestration_rejected`.

- API
  - `POST /api/orchestration/propose`
  - `POST /api/orchestration/apply`
  - `POST /api/orchestration/reject`

- Dashboard
  - Shows prepared/applied/rejected proposals.
  - Shows whether proposal has proposed tasks/approvals.
  - Shows that proposals do not execute actions.

## Safety rules

Applying a proposal may only create local control-plane rows:

- `direct_answer`: no task, no approval.
- `refuse_redirect`: no task, no approval.
- `research_agent`: one planned task, no approval.
- `task_queue`: one planned task, no approval.
- `approval_required`: one task linked to one pending approval with expected change, risk, rollback and failure-mode details.

Applying a proposal never:

- starts an agent run;
- consumes an approval;
- approves an approval;
- calls OpenAI/Codex;
- shells out;
- installs packages;
- reads `.env.local` values;
- connects accounts;
- performs external writes.

The existing approval decision endpoint remains unchanged:

- `POST /api/decision`
- request shape: `{id, choice, note?}`
- approval rejection still blocks the linked task.
- rejected high-risk approval plans are fingerprinted and cannot be retried unless the proposed plan changes.

## Verification

Required local checks:

```bash
PYTHONPATH=/home/per/leon-ai-assistant/src python3 -m py_compile \
  src/leon_control_plane/server.py \
  src/leon_control_plane/store.py \
  src/leon_control_plane/model_policy.py \
  src/leon_control_plane/decision_layer.py \
  src/leon_control_plane/agent_runtime.py \
  src/leon_control_plane/orchestrator.py \
  tests/test_control_plane.py

./scripts/leon-routing-eval --no-record
```

Manual/API checks performed:

- `research_agent` proposal applied -> task only.
- `approval_required` proposal applied -> task plus pending approval.
- Existing `/api/decision` rejection -> linked task blocked.
- Secret-like prompt redacted in proposal/state/audit.
- `/api/audit/validate` remains true.
