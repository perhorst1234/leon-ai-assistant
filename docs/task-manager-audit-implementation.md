# Leon AI Assistant — Task Manager + Audit implementation

Status: implemented slice, in review.

## Runtime source of truth

Mutable runtime state now lives in:

```text
state/control-plane.sqlite
```

That file is ignored by git. `state/control-plane.seed.json` remains the startup seed/config source. `state/control-plane.json` is no longer the intended mutable source of truth and is ignored.

## Implemented

- SQLite-backed phases, tasks, approvals, env registry, engineering rules and audit events.
- Idempotent seeding from `state/control-plane.seed.json`.
- Dashboard API reads from SQLite.
- Task create API.
- Task status transition API.
- Task metadata for value score, source references and parent/subtask relations.
- Derived per-task approval status and recent audit snippets in `/api/state`.
- Approval decision API.
- Approval consume API.
- Secret update audit event with redacted payload.
- Audit validation API.
- Recent audit events shown in the dashboard.
- Audit hash-chain with `prev_hash` and `event_hash`.
- SQLite triggers blocking `UPDATE` and `DELETE` on `audit_events`.

## Enforced task rules

Allowed statuses:

```text
new
planned
active
waiting_for_approval
waiting_for_secret
waiting_for_user
blocked
review
done
rejected
```

Important backend checks:

- New tasks may only start as `new` or `planned`; gated/terminal states must go through the transition API.
- `done` requires `result` and `verification_note`.
- `blocked` requires `blocked_reason`.
- `rejected` requires `review_note`.
- `waiting_for_approval` requires a pending `approval_id`.
- `waiting_for_secret` requires a registered secret key.
- terminal tasks require explicit reopen to move back to `planned`.
- Task title, goal, acceptance criteria, source refs, result, verification notes, review notes and blocked reason reject OpenAI-style secret-like values.

## Task manager fields

Task records exposed by `/api/state` now include:

- `owner`
- `status`
- `risk_level`
- `value_score` from 0 to 5
- `source_refs`
- `parent_task_id`
- `subtasks`
- `subtask_count`
- `approval_required`
- `approval_status`
- `approval_id`
- `approval_gate_summary`
- recent per-task `audit_events`

## Audit event fields

Audit events include:

- `id`
- `sequence`
- `timestamp`
- `actor_type`
- `actor_id`
- `event_type`
- `task_id`
- `approval_id`
- `risk_level`
- `summary`
- `evidence`
- `redacted_payload_json`
- `prev_hash`
- `event_hash`

## Verification performed

Commands run:

```bash
PYTHONPATH=/home/per/leon-ai-assistant/src python3 -m py_compile src/leon_control_plane/server.py src/leon_control_plane/store.py src/leon_control_plane/model_policy.py tests/test_control_plane.py
```

Direct checks covered:

- env key validation;
- env quoting;
- invalid task transition rejected;
- invalid initial create statuses rejected;
- `done` without `verification_note` rejected;
- valid `new -> planned -> active -> review -> done`;
- value/source/subtask metadata exposed in state;
- derived approval status exposed on task state;
- HTTP task create stores value/source/parent metadata and rejects gated initial statuses;
- audit hash-chain valid;
- audit `UPDATE` blocked;
- audit `DELETE` blocked;
- secret audit metadata does not contain raw secret values.

Live checks covered:

- `GET /api/state` returns SQLite-backed runtime state.
- `POST /api/audit/validate` returns `valid: true`.
- `.env.local` is git-ignored.
- `state/control-plane.sqlite` is git-ignored.
- restart preserves SQLite state and valid audit chain.

## Not done yet

- Full task edit UI for every metadata field.
- Rich approval creation UI.
- Dashboard authentication before relying on remote Tailscale controls.
- Agent runtime adapter.
- External tool/MCP integrations.
