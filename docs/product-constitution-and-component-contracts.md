# Leon AI Assistant — constitution and component contracts

Status: v1 contract  
Source: `docs/personal-ai-assistant-plan.md`  
Rule: this document defines product boundaries; implementation details live in separate slice docs.

## Constitution

Leon is a local-first personal AI assistant that helps with live questions, deep research, task management, tool use and self-improvement. Leon is not a fully autonomous actor. It must route, explain, log and wait for approval when risk is material.

### Non-negotiable rules

1. Control plane first: tasks, approvals, env intake, audit and review gates must exist before autonomous capabilities.
2. Read-only by default: new tools, accounts and integrations start read-only.
3. Keep moving when safe: normal local docs/code/dashboard work inside this project does not need user approval every time.
4. Approval before real impact: spending money, financial actions, account connections, external writes, public posts, server changes, broad destructive actions, large downloads, model downloads and GPU-heavy jobs need explicit user approval.
5. Secrets are capability inputs, not agent context: agents may know whether an env key is present, not the raw value.
6. Every meaningful action is traceable: route, proposal, assignment, agent run, tool call, approval, failure and review have durable audit evidence.
7. Local machine first: Leon must work without a GPU; GPU/cloud routes are optimizations.
8. Reuse before build: evaluate existing projects/MCP servers before custom work, but never install/run them without fit, security and maintenance review.
9. User correction wins: memory, tasks, preferences and plans must be visible and correctable.

### Risk classes

| Risk | Examples | Default gate |
|---|---|---|
| Low | text rewrite, summary, local status read | direct/tool route allowed |
| Medium | project code planning, memory candidate, research | task/review gate |
| High | money, account connection, external write, server mutation, install, GPU-heavy job | approval gate |
| Refuse | captcha bypass, spam, credential theft, malware, destructive broad target | refuse and redirect |

## Component contracts

### Shared component contract template

Every major component must declare:

- primary responsibility;
- owner role;
- inputs and outputs;
- owned state;
- allowed actions;
- forbidden actions;
- approval triggers;
- audit events;
- failure states;
- required evidence/tests;
- user-visible controls.

### Responsibility matrix

| Component | Primary responsibility | Owner role | Does not own |
|---|---|---|---|
| Control Plane | Operational visibility, tasks, approvals, env status, audit | Backend/PM Agent | Final assistant UX |
| Assistant Interface | User-facing Leon experience, later specified with user | UI/Experience Agent | Safety decisions |
| Personal Agent | Live conversation and routing orchestration | Personal Agent | Long research, installs, external writes |
| Decision Layer | Route/risk/value/model decision before work | Decision/Value Engine | Execution |
| Task Manager | Durable work state and review lifecycle | Backend Agent | Tool execution |
| Orchestration | Convert routes to reviewable local proposals | Orchestration Agent | Agent execution |
| Agent Runtime | Run bounded agent packets through selected adapter | Runtime Agent | Approval policy |
| Agent Assignment | Create/review/apply assignment proposals | Reviewer/Runtime Agent | Permission expansion |
| Research Agent | Finite research jobs with source quality | Research Agent | Installing or running unknown repos |
| Memory/Graph | Explainable continuity and relationships | Memory Agent | Hidden profiling |
| MCP/Tools | Tool registry, GitHub/MCP candidate scoring, scopes, manifests and enforcement | Tool Builder Agent | User approval decisions or executing unreviewed repos |
| Planner/Manager | Read-first specialized integrations | Planner/Manager Agent | External writes without approval |
| Night Improvement | Proposal generation and morning reports | Self Learning Agent | Silent execution |
| Model Scheduler | Model route, cost/privacy/resource policy | Model Scheduler Agent | Starting GPU-heavy jobs without approval |
| Security/Governance | Risk taxonomy, data classes, audit, incident policy | Security Agent | Product feature shortcuts |

### Control Plane

- Responsibility: show progress, tasks, approvals, env status, audit, routing, proposals and agent reviews.
- Inputs: SQLite state, `.env.local` key presence, user decisions.
- Outputs: safe dashboard state, task/approval/proposal mutations, audit events.
- Must not: expose secret values or claim execution happened when only a proposal was made.
- Acceptance: remote dashboard is token-gated; audit hash-chain validates.

### Leon Assistant Interface and Experience

- Responsibility: eventual user-facing Leon experience. Its exact shape is intentionally deferred.
- Inputs: user messages, route decisions, task state, memory previews, approval needs.
- Outputs: responses, previews, questions, safe UI states.
- Must not: bypass control-plane gates for smoother UX.
- Acceptance: interface contract exists before building; UI distinguishes answer, proposal, waiting state and executed action.

### Personal Agent

- Responsibility: primary user-facing orchestrator for live questions and task routing.
- Inputs: user request, current context, memory summaries, tool availability.
- Outputs: direct answer, route decision, task/proposal request or refusal.
- Must not: install tools, read raw secrets, start heavy research silently or execute high-risk writes.
- Acceptance: every non-trivial action passes Decision Layer and is attached to a task/proposal/audit record.

### Decision Layer and Value Engine

- Responsibility: decide route, execution path, risk, complexity, value, urgency, source/tool need and model route before work starts.
- Inputs: user text, task context, policy config.
- Outputs: `direct_answer`, `clarification_required`, `quick_tool_use`, `memory_retrieval`, `shell_agent_flow`, `research_agent`, `task_queue`, `approval_required` or `refuse_redirect`.
- Must not: execute tools or external calls.
- Acceptance: routing evalset passes and high-risk cases never become direct execution.

Value score v1:

```text
value_score =
  user_goal_relevance
  + expected_time_saved
  + reuse_or_learning_value
  + urgency
  - risk_penalty
  - cost_or_resource_penalty
  - maintenance_penalty
```

Bands:

| Score | Handling |
|---:|---|
| 0-24 | reject/archive unless user explicitly asks |
| 25-49 | backlog P2 |
| 50-69 | planned P1 |
| 70-89 | high-value queue P0/P1 |
| 90-100 | high-value, but still gated if risky |

### Task Manager and Orchestration

- Responsibility: persist tasks, status, owner, risk, acceptance criteria, proposals and review flow.
- Inputs: route decisions, user-created tasks, agent results.
- Outputs: planned/active/waiting/review/done/blocked task state.
- Must not: mark done without result and verification evidence.
- Acceptance: invalid transitions fail; proposal apply is idempotent; audit remains valid.

### Agent Runtime and Agent Teams

- Responsibility: assign bounded work to local/mock or future provider-backed agents.
- Inputs: task packet, assignment proposal, model route, allowed/forbidden actions.
- Outputs: reviewable agent run with result summary and evidence.
- Must not: start real provider/tool execution outside assignment/provider gates.
- Acceptance: active runtime remains `local_mock` until provider adapter approval criteria are implemented.

### Research Agent

- Responsibility: handle complex, multi-source tasks with source quality and trade-off reporting.
- Inputs: research task, scope, source policy, stop condition.
- Outputs: report with sources, dates checked, confidence, risks, next actions.
- Must not: install/run unknown repos or treat popularity as security proof.
- Acceptance: research output includes sources, uncertainty and recommendation; no external writes.

### Memory Engine and Knowledge Graph

- Responsibility: maintain explainable continuity and relationships between user, projects, tools, tasks, sources, observations and opportunities.
- Inputs: reviewed memory candidates, user corrections, task evidence.
- Outputs: memory items with type, source, confidence, sensitivity, expiry and graph links.
- Must not: create hidden profiles or store sensitive facts without review policy.
- Acceptance: user can inspect, edit and delete memories; sensitive candidates require review.

### MCP Hub and Tool Registry

- Responsibility: manage tools/MCP servers, scopes, reliability, maintenance risk and approval requirements.
- Inputs: tool candidates, source review, permissions, required env keys.
- Outputs: tool manifest, read/write classification, approval requirements, audit policy.
- Must not: install/connect/run tools before security and fit review.
- Acceptance: every tool has a permission manifest; write tools require consumed approval id.

Minimum tool manifest:

```yaml
tool_id:
name:
owner:
source_url:
purpose:
required_env_keys:
read_scopes:
write_scopes:
risk_level:
resource_profile:
cost_profile:
approval_required_for:
allowed_without_approval:
forbidden_actions:
audit_events:
rollback_notes:
maintenance_status:
```

### Planner, Manager, Browser and Server Integrations

- Responsibility: specialized read-first capabilities for agenda/mail/school, finance/shopping/tickets, browser research and server status.
- Inputs: scoped tool manifests and user-approved credentials.
- Outputs: read-only summaries, previews, draft actions, approval cards.
- Must not: send, buy, bid, trade, pay, write calendar events, mutate servers or bypass anti-bot systems without explicit approval.
- Acceptance: every write/action path generates preview + approval; read paths hide raw secrets.

### Night Improvement and Feedback Engines

- Responsibility: propose improvements, detect repeated friction, score opportunities and prepare morning reports.
- Inputs: reviewed task history, feedback, tool reliability, memory candidates.
- Outputs: proposals, queue items, morning report, rejected/archived ideas.
- Must not: install tools, connect accounts or change user data while the user is away.
- Acceptance: night work produces proposals only; user-facing report separates facts from suggestions.

### UI Composition, Character and Experience Engine

- Responsibility: later map task state to appropriate experience, assistant presence and friction scoring.
- Inputs: route, task state, approval state, memory state, interaction feedback.
- Outputs: UI composition choice, character/status signal, experience metrics.
- Must not: hide risk or make proposals look executed.
- Acceptance: component rules preserve safety states and user control.

### Model Scheduler and GPU Routing

- Responsibility: choose between Luna/Terra/Sol/cloud/local routes based on task type, privacy, cost, latency and hardware readiness.
- Inputs: task type, complexity, risk, budget mode, privacy level, GPU state.
- Outputs: model route with reason.
- Must not: require GPU for core product or start model downloads/GPU jobs without approval.
- Acceptance: model route reason is visible; local GPU remains optional until benchmark evidence exists.

### Security, Governance and Observability

- Responsibility: keep autonomy bounded while allowing efficient local progress.
- Inputs: routes, tasks, approvals, env key presence, audit events, tool manifests.
- Outputs: risk decisions, audit checks, incident notes, rollback requirements.
- Must not: weaken policy for convenience or hide uncertainty.
- Acceptance: `config/autonomy-policy.json` defines what can continue without user approval and what must stop.

Data classes:

| Class | Examples | Handling |
|---|---|---|
| Public | docs, public repo metadata | may be used in prompts |
| Internal | Leon implementation details | project-local only unless approved |
| Personal | preferences, calendar summaries | scoped use, review before persistence |
| Sensitive | finance, school, account data | strict scopes, approval for writes |
| Secret | API keys, passwords, tokens | never shown to agents/logs/audit |

Tool/MCP policy:

- Existing GitHub projects are preferred over custom implementation when they are fit-for-purpose and lower total risk/maintenance.
- Every repo/MCP server first becomes a candidate manifest with source URL, use case, scopes, env keys, cost/resource profile and forbidden actions.
- Candidate/reviewed tools cannot execute. Only `approved_readonly` and `approved_write_gated` statuses can pass runtime checks.
- Every future tool call must pass the local permission preflight gate before execution.
- Raw secret reads, spending, account connection, installs, external writes and resource-heavy jobs remain gated by explicit policy/approval.

Incident policy:

- stop the current action;
- preserve evidence without secrets;
- mark task blocked or rejected;
- record audit event;
- propose rollback or cleanup;
- ask user only when required by `config/autonomy-policy.json`.

## Definition of done for a component slice

A component slice is done only when:

- contract and acceptance criteria are documented;
- state/API/dashboard behavior exists where relevant;
- tests or live checks cover the acceptance criteria;
- audit hash-chain remains valid;
- secrets are not exposed;
- risky external effects are blocked behind approval;
- reviewer decision is recorded.

## Current build order

1. Finish control-plane foundations and core intelligence gates.
2. Build MCP/tool permission model before real integrations.
3. Add provider adapter shell for OpenAI Agents SDK, disabled by default.
4. Add memory/graph MVP.
5. Add user-facing Leon interface only after its product contract is specified with the user.
