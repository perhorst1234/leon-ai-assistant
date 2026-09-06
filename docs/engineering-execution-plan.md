# Leon AI Assistant — product/engineering execution plan

Status: working plan  
Source: `docs/personal-ai-assistant-plan.md`  
Constraint: local-first machine, approval-first external actions, secure credential intake, no autonomous destructive/write actions.

## 1. Execution principles

1. Build the control plane before autonomous capability.
2. Prefer reuse, then adapt, then wrap, and only build from scratch when reuse is unsafe or inefficient.
3. Default every external integration to read-only.
4. Treat secrets as write-only from the assistant's perspective: the user can provide them through the dashboard, but agents must never see or print raw values.
5. Every agent task must produce reviewable evidence: files changed, tests run, risks, open questions, and rollback path.
6. The local machine is the primary runtime. GPU acceleration is optional and must not be a hard dependency.

## 2. Phase roadmap

### Phase 0 — Constitution and governance

Goal: define the rules that prevent the assistant from becoming an uncontrolled collection of agents and tools.

P0:

- Gaia/Leon Constitution v1: mission, autonomy limits, tool policy, memory policy, review policy.
- Approval matrix for installs, code changes, account access, mail/calendar writes, payments, server changes, and public actions.
- Definition of done for agent work.
- Risk taxonomy: privacy, money, account, infrastructure, public effect, destructive action, cost.

P1:

- Component responsibility matrix.
- Data classification model: public, internal, personal, sensitive, secret.
- Incident and rollback policy.

P2:

- Weekly Evolution Journal format.
- Product decision log.

Acceptance criteria:

- Every high-risk action maps to an approval requirement.
- Every major component has exactly one primary responsibility.
- No agent can claim completion without reviewable evidence.

Risk gate:

- Do not start autonomous or external-tool agents before this phase is accepted.

Subagent candidates:

- Product spec agent: extract constitution draft from plan.
- Security review agent: test approval matrix for missing high-risk cases.
- QA agent: convert approval cases into test scenarios.

### Phase 1 — Control plane dashboard

Goal: give the user and reviewer a single place to monitor progress, answer blockers, approve actions, and provide credentials safely.

P0:

- Dashboard IA: Home, Tasks, Approvals, Secrets, Agents, Audit Log.
- Task cards with phase, priority, status, owner, blocked reason, next review.
- Approval queue with action preview, risk, scope, cost, rollback, expiry.
- Secure API-key intake: masked input, validation, env target selection, no secret echo.
- Audit log contract for user approvals, agent actions, tool calls, and failures.

P1:

- “Need input” queue for user decisions.
- Morning Brief panel.
- Read-only system status panel.

P2:

- Evolution Journal panel.
- Opportunity/Curiosity proposal panels.

Acceptance criteria:

- User can see what is being worked on, what is blocked, and what needs approval.
- Secrets are never stored in plain project docs, printed in logs, or sent to agents as visible text.
- Every approved external action has a durable approval record.

Risk gate:

- No real API integrations before secret intake and audit log are implemented.

Subagent candidates:

- UX agent: dashboard flows and wireframes.
- Backend agent: task/approval/audit data contracts.
- Security agent: secret redaction and env-write threat model.

### Phase 2 — Task manager and agent work protocol

Goal: make long-running work decomposable, reviewable, and resumable.

P0:

- Task schema: id, title, goal, owner, priority, risk, status, sources, subtasks, result, acceptance criteria.
- Agent assignment protocol: task packet, allowed actions, forbidden actions, output contract.
- Review protocol: accept, request changes, reject, escalate.
- Local sandbox policy for code/browser/terminal work.

P1:

- Research Agent skeleton design: planner, workers, source-quality, report writer.
- Worker result schema.
- Retry and stop rules.

P2:

- Night Queue design.
- Auto-generated morning task proposals.

Acceptance criteria:

- Every subagent task can be executed without needing hidden context.
- Reviewer can reject work with precise feedback.
- Task state survives interruption and restart.

Risk gate:

- No multi-agent code work against the main repo until review/rollback is defined.

Subagent candidates:

- Architecture agent: task schema and orchestration comparison.
- QA agent: lifecycle edge cases.
- Documentation agent: agent operating manual.

### Phase 3 — Decision Layer and Value Engine

Goal: route requests correctly before spending compute, touching tools, or asking for unnecessary permission.

P0:

- Route classifier: direct answer, quick read-only tool, research, queue, approval required, refuse/redirect.
- Complexity scoring with the 30-second rule.
- Risk scoring.
- Value Engine v1 formula and score bands.
- Routing eval set with representative user requests.

P1:

- Source-quality scoring.
- Confidence model.
- Cost/latency estimate.

P2:

- Backlog auto-prioritization.
- Opportunity scoring.

Acceptance criteria:

- Routing eval passes for simple, complex, risky, and blocked examples.
- High-risk external actions always route to approval.
- Low-value/high-risk suggestions are archived or rejected.

Risk gate:

- No broad tool access before routing and risk evals are passing.

Subagent candidates:

- Eval agent: create routing test set.
- Security agent: adversarial risk cases.
- Product agent: score model calibration.

### Phase 4 — Local-first runtime and model routing

Goal: run reliably on the local machine now, with optional later Tesla M40/P40 support.

P0:

- Runtime decision document: OpenAI Agents SDK vs LangGraph vs VoltAgent or alternative.
- Model router contract: task type, privacy level, expected latency, cost, local/external route.
- Hardware inventory checklist.
- External model fallback policy.

P1:

- LiteLLM/Ollama/llama.cpp prototype plan.
- Local small-model task classes: summarization, classification, drafts, low-risk transforms.
- GPU benchmark plan for P40/M40.

P2:

- vLLM or other serving tests if hardware supports it.
- Model performance dashboard.

Acceptance criteria:

- System remains usable without GPU.
- Model decisions are logged with reason, cost class, and privacy class.
- GPU-intensive jobs require an explicit resource policy.

Risk gate:

- Do not design the product around M40/P40 until benchmark evidence exists. P40 is likely more practical than M40, but both are old enough that driver/CUDA/model-serving compatibility must be proven.

Subagent candidates:

- Infra agent: hardware inventory and driver risk report.
- ML agent: local model serving comparison.
- Benchmark agent: workload benchmark design.

### Phase 5 — Memory and Knowledge Graph

Goal: build useful continuity without unsafe or opaque memory.

P0:

- Memory CRUD and review queue.
- Memory types: session, working, long-term, episodic, negative.
- Confidence, source, expiry, sensitivity, and linked project fields.
- User-visible memory delete/edit controls.

P1:

- Knowledge Graph entity schema.
- Privacy filter before permanent storage.
- Memory conflict handling.

P2:

- Evaluation of Mem0, Graphiti, Cognee, OpenViking with the same dataset.

Acceptance criteria:

- User can inspect and delete what Leon remembers.
- Sensitive memory requires review before becoming long-term.
- No raw secrets are stored as memory.

Risk gate:

- No automatic long-term memory until review, expiry, and deletion work.

Subagent candidates:

- Data agent: schema and migration plan.
- Privacy agent: PII/secrets detection tests.
- Research agent: memory tooling evaluation.

### Phase 6 — MCP Hub and integrations

Goal: safely connect tools without creating hidden authority.

P0:

- Tool registry schema.
- Permission manifest per tool/MCP server.
- Read-only default policy.
- Reliability tracking.
- Integration evaluation template.

P1:

- Browser/research tool evaluation: Playwright MCP, Browser Use, Firecrawl, Apify.
- Calendar/mail preview-only pilot.
- Server Manager read-only monitoring pilot.

P2:

- Shopper/deal pilot.
- Finance read-only sandbox.
- Planner integrations.

Acceptance criteria:

- Every tool has declared scopes, risks, and owner.
- Write actions are technically blocked without approval.
- Tool failures create diagnosable log entries.

Risk gate:

- No bank, payment, e-mail send, calendar write, shopping purchase, ticket purchase, or server mutation without separate approval flow.

Subagent candidates:

- Tooling agent: GitHub/MCP candidate scoring.
- Security agent: scopes and token risk review.
- QA agent: failure and permission tests.

### Phase 7 — UI Composition Engine

Goal: make the product feel like a controlled AI workspace, not a generic chat app.

P0:

- App shell.
- Home, Chat, Tasks, Approvals, Secrets, Audit spaces.
- Core components: Task Card, Approval Sheet, Context Card, Source Card, Audit Row.
- Component DNA format.

P1:

- Research Space.
- Memory Space.
- Tool Space.
- Morning Brief.

P2:

- Assistant Character states.
- Motion language.
- Opportunity and Curiosity spaces.

Acceptance criteria:

- Simple tasks stay fast and compact.
- Complex tasks expose plan, status, sources, and uncertainty.
- Approval actions are explicit and accessible.
- UI supports keyboard and reduced motion.

Risk gate:

- The AI may compose registered components, but must not invent unreviewed UI patterns for high-risk flows.

Subagent candidates:

- UX agent: interaction flows.
- Frontend agent: component implementation.
- Accessibility agent: WCAG review.

### Phase 8 — Research Agent and Night Improvement

Goal: enable deep work and self-improvement only after governance, tasking, and approvals are reliable.

P0:

- Research Agent finite job execution.
- Source Quality Worker.
- Research report format.
- Night Queue proposals only.

P1:

- Opportunity Engine: MCP/repo/API/model/security scans.
- Curiosity Engine: repeated behavior, tool failures, friction, follow-up burden.
- Morning Brief generation.

P2:

- Experiment tracking.
- Weekly Evolution Journal.
- Low-risk improvements prepared automatically but not applied without policy.

Acceptance criteria:

- Research outputs include method, sources, uncertainty, and next steps.
- Night Cycle creates reviewable proposals, not silent changes.
- Value Engine prioritizes proposals.

Risk gate:

- No self-modifying code, installs, permissions, or account changes without explicit review.

Subagent candidates:

- Browser research agent: gather sources.
- Source-quality agent: score evidence.
- Report writer agent: produce synthesis.
- Reviewer: central acceptance only.

## 3. Immediate build order

Recommended first implementation slice:

1. Project constitution and approval matrix.
2. Control plane dashboard skeleton.
3. Task/approval/audit data model.
4. Secure API-key intake flow.
5. Agent work protocol and review queue.

Reason: everything else depends on control, secrets, auditability, and task ownership. Building tools, memory, or autonomous agents before this creates rework and unnecessary risk.

## 4. Hardware and GPU policy

Baseline:

- Leon must run on CPU/local machine with external-model fallback.
- GPU support is an optimization, not a dependency.

Tesla M40/P40 considerations:

- Treat both as experimental until benchmarked on the actual machine.
- Confirm power, cooling, driver, CUDA, VRAM, quantization, and serving-stack support.
- Prefer workload-level benchmarks over synthetic tokens/sec only.
- Do not schedule heavy local model jobs by default.

Acceptance criteria for GPU enablement:

- Stable driver and model-serving setup.
- Repeatable benchmark results.
- Thermal/power check passes.
- Model router can fall back when local inference fails.

## 5. Approval-first external action policy

Actions requiring approval:

- Installing packages, MCP servers, browser extensions, services, models, drivers.
- Writing to calendar, e-mail, files outside approved scope, databases, or remote systems.
- Sending messages, posting publicly, buying, bidding, paying, trading.
- Restarting containers, changing firewall/DNS, modifying server config.
- Connecting personal accounts or importing sensitive data.

Approval record must include:

- Proposed action.
- Reason.
- Affected systems.
- Permissions/scopes.
- Cost estimate.
- Risk level.
- Rollback path.
- Expiry.
- User approval timestamp.

## 6. Subagent task packet template

```yaml
task_id:
title:
phase:
priority: P0 | P1 | P2
goal:
context_files:
allowed_actions:
forbidden_actions:
expected_output:
acceptance_criteria:
risk_notes:
reviewer:
deadline_or_stop_condition:
```

## 7. Review acceptance template

```yaml
review_status: accepted | changes_requested | rejected
evidence_reviewed:
tests_or_checks:
security_notes:
product_notes:
required_changes:
follow_up_tasks:
```
