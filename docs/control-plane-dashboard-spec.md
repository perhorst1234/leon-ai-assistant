# Leon AI Assistant — control plane dashboard spec

Status: product/engineering specification  
Purpose: provide visibility, approvals, safe credential intake, and agent review for the Leon AI Assistant project.

## 1. Product requirement

The dashboard is the operational control plane for Leon. It must let the user:

- See current project progress.
- See what agents are doing.
- Approve or reject risky actions.
- Provide API keys and credentials safely.
- Answer blockers without giving secrets directly to chat or agents.
- Review audit history.

The dashboard is not a generic admin panel. It is the safety layer that makes agentic work acceptable.

## 2. Spaces

### Home

Shows:

- Current phase.
- P0 blockers.
- Active tasks.
- Approvals waiting.
- Questions needing user input.
- Last completed review.

Acceptance criteria:

- User can understand project state in under 30 seconds.
- Home does not expose secrets or raw logs by default.

### Tasks

Shows:

- Backlog by phase and priority.
- Active tasks.
- Subagent assignments.
- Status: new, planned, active, waiting_for_approval, blocked, review, accepted, rejected, done.
- Acceptance criteria and evidence.

Acceptance criteria:

- Every task has owner, priority, risk, and next action.
- Tasks can be filtered by P0/P1/P2, phase, blocked, approval-needed, and review-needed.

### Approvals

Shows:

- Proposed action.
- Why it is needed.
- External effect.
- Scope and permissions.
- Cost.
- Risk.
- Rollback.
- Expiry.
- Approve/reject controls.

High-risk examples:

- Install package or service.
- Connect Gmail/Calendar/GitHub/bank/payment account.
- Send e-mail or calendar invite.
- Restart container or edit server config.
- Download large model or start GPU-heavy job.

Acceptance criteria:

- No write/external action can execute without an approval id.
- Approval text is specific enough that the user knows what will happen.
- Approvals expire and cannot be silently reused for a different action.

### Secrets

Shows:

- Required credential name.
- Service.
- Purpose.
- Target env file or secret store.
- Validation status.
- Last rotated timestamp.
- Masked fingerprint only.

Does not show:

- Raw API keys.
- Passwords.
- OAuth refresh tokens.
- Full secret values in logs.

Acceptance criteria:

- Secret input is write-only from the assistant perspective.
- The user chooses the destination before the value is written.
- The dashboard stores only metadata and masked fingerprints in normal app data.
- Failed validation never prints the secret.

### Agents

Shows:

- Agent role.
- Assigned task.
- Allowed actions.
- Current state.
- Last heartbeat.
- Output pending review.

Agent states:

- idle
- planning
- working
- waiting_for_input
- waiting_for_approval
- failed
- ready_for_review
- accepted

Acceptance criteria:

- User can pause an agent.
- Reviewer can see what context and permissions the agent had.
- Agents cannot expand their own permissions.

### Audit Log

Shows:

- Timestamp.
- Actor: user, reviewer, agent, system.
- Action.
- Target.
- Tool/service.
- Approval id if applicable.
- Result.
- Risk level.
- Redacted metadata.

Acceptance criteria:

- Every external tool call is logged.
- Every approval decision is logged.
- Secrets are redacted.
- Logs are useful for debugging without exposing sensitive data.

## 3. Data contracts

### Task

```yaml
id:
title:
phase:
priority: P0 | P1 | P2
owner_type: user | reviewer | agent | system
owner_id:
status:
risk_level: low | medium | high | critical
goal:
context:
allowed_actions:
forbidden_actions:
acceptance_criteria:
subtasks:
evidence:
blocked_reason:
created_at:
updated_at:
```

### Approval

```yaml
id:
task_id:
requested_by:
action_type:
summary:
reason:
affected_systems:
permissions:
external_effect:
cost_estimate:
risk_level:
rollback_plan:
expires_at:
status: pending | approved | rejected | expired | consumed
approved_by:
approved_at:
consumed_at:
```

### Secret request

```yaml
id:
service:
credential_name:
purpose:
required_scopes:
target:
status: requested | provided | validated | failed | rotated | revoked
masked_fingerprint:
last_validated_at:
created_at:
updated_at:
```

### Agent run

```yaml
id:
task_id:
agent_role:
status:
input_context_refs:
allowed_actions:
forbidden_actions:
started_at:
last_heartbeat_at:
completed_at:
result_summary:
evidence_refs:
review_status:
```

### Audit event

```yaml
id:
timestamp:
actor_type:
actor_id:
event_type:
task_id:
approval_id:
tool:
target:
risk_level:
result:
redacted_payload:
```

## 4. Safe API-key intake flow

1. System creates `SecretRequest`.
2. Dashboard shows why the credential is needed and what scopes are required.
3. User chooses target destination:
   - local `.env` for development,
   - local secret store,
   - external vault later if approved.
4. User enters secret in masked input.
5. Backend writes secret to selected destination.
6. Backend validates the credential if validation is safe and read-only.
7. Dashboard stores only metadata and masked fingerprint.
8. Audit log records the secret request and validation result, never the value.

Hard rules:

- Never paste secrets into chat.
- Never commit secrets.
- Never print secrets during validation.
- Never send secrets to subagents as text.
- Never reuse a credential for a broader scope than approved.

## 5. Approval execution flow

```text
Agent/system proposes action
  ↓
Risk classifier marks approval required
  ↓
Approval card created
  ↓
User approves or rejects
  ↓
If approved: one bounded action may execute
  ↓
Approval marked consumed
  ↓
Audit event written
```

An approval is invalid if:

- The target changed.
- The permission scope changed.
- The action became more destructive.
- The cost changed materially.
- The approval expired.

## 6. MVP dashboard acceptance checklist

P0 checklist:

- Home shows current phase and P0 blockers.
- Tasks list supports phase, priority, status, risk.
- Approvals can be created, approved, rejected, consumed, expired.
- Secrets can be requested and marked provided without exposing raw value.
- Audit events record tool/action/approval metadata.
- Agent runs are visible and reviewable.

P1 checklist:

- Morning Brief panel exists.
- Need Input queue exists.
- Tool registry summary exists.
- Basic search/filter exists.

P2 checklist:

- Opportunity and Curiosity cards exist.
- Evolution Journal exists.
- Model/hardware status appears.

## 7. Non-goals for MVP

- No automatic purchasing, paying, bidding, trading, or sending.
- No self-installing MCP servers.
- No autonomous server mutation.
- No opaque memory system.
- No dependency on a Tesla GPU.
- No complex animated assistant character before the control plane is useful.

## 8. First implementation slice

Recommended first slice:

1. Static dashboard shell.
2. Task list using local storage or local DB.
3. Approval queue.
4. Secret request metadata UI.
5. Audit log.

Only after this slice works should real external integrations be added.
