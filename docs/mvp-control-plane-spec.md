# Leon AI Assistant — MVP Control Plane Spec

Status: working specification  
Scope: local-first MVP on this machine  
Source vision: `docs/personal-ai-assistant-plan.md`

## 1. Decision

Build the first MVP as a local control plane before adding agent runtime, memory, graph, observability, browser automation, workflow automation or GPU routing.

Reason: the product vision depends on traceability, approvals, safe secrets and task continuity. Agents without those foundations become hard to debug and unsafe to delegate to.

## 2. MVP objective

The MVP must let the user and project manager see, control and unblock the project locally:

- what is being worked on;
- which phase and task each item belongs to;
- what is waiting for approval, user input or a secret;
- what changed, why it changed and how it was verified;
- which secrets are present without revealing the values;
- which work must not start yet.

The MVP does not need to answer general user chat prompts yet. It is the operating layer that later agents will use.

## 3. Recommended first implementation shape

Recommended initial stack:

- Backend: Python + FastAPI.
- Storage: SQLite.
- UI: server-rendered HTML with Jinja or simple HTMX-style progressive enhancement.
- Runtime: local process only.
- Secrets target: local `.env` file outside git, with `.env.example` for names only.

Why this stack:

- Python aligns with later LangGraph/OpenAI Agents SDK/Pydantic AI options.
- SQLite is enough for tasks, approvals, audit events and local status.
- Server-rendered UI keeps the first dashboard small and debuggable.
- It avoids installing n8n, Langfuse, vector databases or model servers before the control model is stable.

Trade-off: this is not the final premium UI. It is a correct local operator console. A richer React/Tauri UI can replace or wrap it later once the data model and approval semantics are proven.

## 4. MVP modules

### 4.1 Dashboard

Purpose: one screen for project state.

Must show:

- active phase;
- active tasks;
- blocked tasks;
- approval requests;
- missing secrets;
- recent audit events;
- next recommended action.

Must not show:

- raw secret values;
- full logs by default;
- speculative future modules as if they are implemented.

Acceptance criteria:

- user can open the dashboard locally;
- user can identify the current bottleneck in under 30 seconds;
- every card links to the task, approval or secret that caused it.

### 4.2 Task Manager

Purpose: source of truth for long-running work.

Minimum fields:

- `id`
- `title`
- `goal`
- `phase`
- `owner`
- `status`
- `priority`
- `risk_level`
- `approval_required`
- `blocked_reason`
- `created_at`
- `updated_at`
- `done_at`

Allowed statuses:

- `new`
- `planned`
- `active`
- `waiting_for_approval`
- `waiting_for_secret`
- `waiting_for_user`
- `blocked`
- `review`
- `done`
- `rejected`

Acceptance criteria:

- tasks can be created, edited, blocked, moved to review and marked done;
- blocked work remains visible rather than silently stopping progress;
- every done task has a result and verification note.

### 4.3 Approval Center

Purpose: prevent unsafe or external-impact actions from happening silently.

Approval request fields:

- `id`
- `task_id`
- `action_type`
- `summary`
- `risk_level`
- `requested_by`
- `required_before`
- `decision`
- `decision_note`
- `created_at`
- `decided_at`

Approval required for:

- installs;
- dependency upgrades;
- code execution outside the project;
- external account connection;
- email/calendar/write actions;
- payments, purchases, trading or finance actions;
- destructive file/database/container changes;
- model downloads or GPU-intensive local jobs;
- secrets creation or scope expansion.

Acceptance criteria:

- dangerous action cannot be represented as a normal task step;
- approval captures what will happen, why, risk and rollback/exit path;
- declined approvals move related work to rejected or blocked with a reason.

### 4.4 Secrets Intake

Purpose: let the user provide API keys or tokens without exposing values to agents or logs.

MVP behavior:

- UI shows required secret name, purpose and scope.
- user enters value into a password-style input;
- backend writes to `.env`;
- dashboard stores only metadata: name, present yes/no, last updated, required by task;
- value is never displayed after submission;
- logs never include values.

Recommended `.env` convention:

```text
OPENAI_API_KEY=
GOOGLE_CALENDAR_CLIENT_ID=
GOOGLE_CALENDAR_CLIENT_SECRET=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

Important limitation:

An env file is acceptable for a local MVP, but it is not a strong secret boundary if agent code can read arbitrary files. Before autonomous agents can run, the runtime must enforce that agents receive capabilities, not raw secret values.

Acceptance criteria:

- `.env` is ignored by git;
- `.env.example` may contain names only;
- missing secrets appear as dashboard blockers;
- no task output or audit event includes raw secret material.

### 4.5 Audit Log

Purpose: make decisions and changes traceable.

Minimum event fields:

- `id`
- `timestamp`
- `actor`
- `event_type`
- `task_id`
- `summary`
- `evidence`
- `risk_level`
- `metadata_json`

Required event types:

- `task_created`
- `task_status_changed`
- `approval_requested`
- `approval_decided`
- `secret_declared`
- `secret_updated`
- `file_changed`
- `verification_run`
- `review_feedback`
- `blocker_added`
- `blocker_resolved`

Acceptance criteria:

- every material state change writes an audit event;
- audit events are append-only in normal UI flows;
- secret values are redacted by construction, not just by display.

## 5. Non-goals for the MVP

Do not build or install now:

- Langfuse;
- n8n or Activepieces;
- OpenAI Agents SDK, LangGraph, CrewAI, AutoGen, VoltAgent or OpenHands as runtime;
- MCP server catalog or external MCP servers;
- browser automation, scraping or shopping agents;
- memory engines, graph databases or vector databases;
- Night Improvement System;
- model scheduler;
- vLLM, Ollama, llama.cpp or local model downloads;
- finance, PayPal, bank, trading, Gmail or Calendar write integrations;
- voice assistant;
- auto-updaters or server-changing automations.

These are later phases after the control plane can track tasks, approvals, secrets and verification.

## 6. Phased execution plan

### Phase 0 — Product control foundation

Deliverables:

- this MVP spec;
- `.gitignore` protecting local env/state;
- initial task decomposition;
- acceptance criteria for every MVP module.

Exit criteria:

- project has a clear local MVP scope;
- agents/builders have task packets with review gates;
- no unsafe dependencies are required.

### Phase 1 — Local dashboard skeleton

Deliverables:

- local app entrypoint;
- dashboard page;
- persistent SQLite database;
- minimal task CRUD;
- audit event creation.

Exit criteria:

- dashboard starts locally;
- tasks persist after restart;
- task changes create audit events.

### Phase 2 — Approvals and blockers

Deliverables:

- approval request model;
- approval list/detail UI;
- blocked task handling;
- status transitions enforced by backend rules.

Exit criteria:

- high-risk actions can only move forward after approval;
- declined approvals leave a visible blocked/rejected state.

### Phase 3 — Safe secrets intake

Deliverables:

- `.env.example`;
- secret registry table;
- secret input UI;
- `.env` writer;
- redaction tests.

Exit criteria:

- user can provide a secret locally;
- dashboard shows presence without value;
- git ignores real secret files;
- logs never contain raw secret values.

### Phase 4 — Agent runtime adapter, still no autonomous agents

Deliverables:

- interface for future agent runs;
- mock agent runner that creates plans/results without external LLM calls;
- task review workflow.

Exit criteria:

- dashboard can represent an agent plan and result;
- project manager/reviewer can accept or reject output;
- no external API key is required yet.

### Phase 5 — First real agent integration

Candidate runtime: decide between OpenAI Agents SDK and LangGraph only after phases 1-4 are stable.

Exit criteria:

- one low-risk agent can work on project-local tasks;
- every run is attached to task, approval and audit records;
- human review remains mandatory for code changes.

## 7. Agent work packets

Use three agent roles once the control plane exists. Until then, use the same roles as manual task labels.

### Builder Agent packet

Scope:

- implements one task at a time;
- may modify only files listed in the task;
- must write a result note and verification command.

Cannot:

- install dependencies without approval;
- read raw secrets;
- touch finance, mail, calendar, browser automation or system services;
- mark its own work accepted.

### Debugger Agent packet

Scope:

- diagnoses failing tests or runtime errors;
- proposes minimal fixes;
- records root cause and evidence.

Cannot:

- broaden scope beyond the failing task;
- hide flaky or unverified behavior;
- skip reproduction if reproducible evidence exists.

### Reviewer Agent packet

Scope:

- reviews diff, architecture fit, security, secrets handling and tests;
- accepts, rejects or requests changes.

Cannot:

- approve work without evidence;
- accept code that leaks secrets to logs/UI;
- accept agent autonomy without approval gates.

## 8. Review gates

Every implementation task must pass:

1. Scope check: matches the task and does not add unapproved systems.
2. Safety check: no raw secrets in code, logs, tests or docs.
3. Persistence check: expected state survives restart where required.
4. Audit check: material changes produce audit events.
5. UX check: dashboard shows the next action or blocker clearly.
6. Test check: relevant tests or manual verification command recorded.

## 9. Current recommended next task

Start Phase 1 with the smallest local app skeleton:

```text
Create a local FastAPI + SQLite control plane with:
- dashboard route
- task model
- audit event model
- seed task for "Build Leon AI Assistant MVP"
- no agent runtime
- no external API calls
- no secret values
```

This should be implemented only after reviewing this spec and choosing whether to proceed with the recommended FastAPI/SQLite path.
