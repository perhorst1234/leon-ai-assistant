# Leon AI Assistant — agent work protocol

Status: operating protocol  
Purpose: define how subagents receive work, produce evidence, and get reviewed.

## 1. Core rule

Subagents do work. The reviewer accepts or rejects work. Subagents do not self-approve, expand scope, install tools, connect accounts, or execute external write actions without an approval record.

## 2. Agent roles

### Product Spec Agent

Good for:

- Turning plan text into requirements.
- Writing acceptance criteria.
- Finding contradictions.
- Preparing decision records.

Forbidden:

- Changing product scope silently.
- Removing safety requirements for speed.

### Architecture Agent

Good for:

- Comparing frameworks.
- Designing data contracts.
- Mapping service boundaries.
- Identifying dependency risks.

Forbidden:

- Installing frameworks without approval.
- Choosing a stack without documented trade-offs.

### Frontend Agent

Good for:

- Building dashboard shell and components.
- Implementing UI states.
- Accessibility fixes.

Forbidden:

- Adding secret display.
- Hiding approval actions behind unclear UI.

### Backend Agent

Good for:

- Task, approval, audit, and secret metadata APIs.
- Local persistence.
- Validation and state transitions.

Forbidden:

- Logging secrets.
- Executing external writes without approval id.

### Security Agent

Good for:

- Threat modeling.
- Scope review.
- Secret handling review.
- Permission tests.

Forbidden:

- Weakening policy to make implementation easier.

### QA Agent

Good for:

- Test plans.
- Regression cases.
- Risk gate checks.
- Acceptance verification.

Forbidden:

- Treating smoke tests as proof of broad safety.

### Research Agent

Good for:

- Evaluating GitHub repos and MCP servers.
- Collecting sources.
- Summarizing trade-offs.

Forbidden:

- Installing or running unknown repos outside a sandbox.
- Treating community popularity as sufficient security proof.

### Infra Agent

Good for:

- Local machine inventory.
- Docker/service planning.
- GPU feasibility checks.
- Monitoring design.

Forbidden:

- Restarting services, changing firewall/DNS, or installing drivers without approval.

## 3. Task packet

Every subagent receives a task packet.

```yaml
task_id:
title:
phase:
priority:
agent_role:
goal:
context_files:
allowed_actions:
forbidden_actions:
expected_output:
acceptance_criteria:
risk_notes:
reviewer:
stop_condition:
```

Minimum allowed actions should be explicit, for example:

```yaml
allowed_actions:
  - read files under docs/
  - propose changes as patch
  - run unit tests
forbidden_actions:
  - install dependencies
  - edit .env files
  - connect external accounts
  - run destructive filesystem commands
```

## 4. Required output

Every subagent result must include:

```yaml
task_id:
summary:
files_changed:
evidence:
tests_or_checks:
risks:
open_questions:
recommended_next_step:
```

For research tasks, include:

```yaml
sources:
  - url:
    authority:
    date_checked:
    relevance:
    risk_notes:
```

For code tasks, include:

```yaml
diff_summary:
tests_run:
test_results:
manual_verification:
rollback_notes:
```

## 5. Review outcomes

Accepted:

- Meets acceptance criteria.
- Evidence is sufficient.
- Risk policy is respected.
- No hidden scope expansion.

Changes requested:

- Direction is right but incomplete or flawed.
- Feedback must be specific and testable.

Rejected:

- Violates scope, safety, architecture, or product direction.
- Requires rework from a clean task packet.

Escalated:

- Needs user decision, credential, external approval, hardware change, or cost approval.

## 6. Risk gates

Approval required before:

- Spending money, paying, trading, buying, bidding or creating financial commitments.
- Connecting APIs or personal accounts.
- Sending email/messages, posting publicly, writing calendar events or changing external account data.
- Installing system packages, drivers, Docker services or external repositories outside an approved sandbox.
- Connecting APIs or personal accounts.
- Large downloads, model downloads, GPU-heavy jobs or actions likely to waste storage, VRAM, power or quota.
- Restarting services or changing infrastructure outside the local Leon dashboard process.
- Destructive filesystem actions outside narrow project-local generated cache cleanup.

Approval is not required for normal project-local docs/code/dashboard work in `/home/per/leon-ai-assistant` when it is reversible, tested, audited where relevant and does not expose secrets or create external side effects.
- Downloading large models or starting GPU-heavy jobs.
- Persisting sensitive personal memory.

Immediate stop required if:

- Secret appears in logs or generated files.
- Agent discovers broader access than expected.
- External service asks for unexpected permissions.
- A destructive command would target a broad or ambiguous path.
- Test or sandbox result contradicts a safety assumption.

## 7. Review checklist

```yaml
scope:
  matches_task: yes/no
  no_unapproved_expansion: yes/no
safety:
  approval_required_respected: yes/no
  secrets_not_exposed: yes/no
  no_unapproved_external_write: yes/no
quality:
  acceptance_criteria_met: yes/no
  tests_or_checks_sufficient: yes/no
  evidence_specific: yes/no
maintainability:
  simple_enough: yes/no
  dependency_risk_acceptable: yes/no
decision:
  status: accepted | changes_requested | rejected | escalated
  required_follow_up:
```

## 8. First useful subagent tasks

These are safe early tasks because they are documentation/research only.

1. Product Spec Agent — draft Gaia Constitution v1 from the plan.
2. Security Agent — turn approval-first policy into concrete threat model.
3. UX Agent — create dashboard wireframes for Home, Tasks, Approvals, Secrets, Audit.
4. Architecture Agent — compare runtime options and recommend one primary stack.
5. QA Agent — create routing and approval test matrix.

These should be completed and reviewed before agents are allowed to modify application code.
