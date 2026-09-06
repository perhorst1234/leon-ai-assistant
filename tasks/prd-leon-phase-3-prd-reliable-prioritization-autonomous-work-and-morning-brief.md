# Leon Phase 3 PRD: Reliable Prioritization, Autonomous Work, and Morning Brief

## Summary
Phase 3 combines Decision Layer, Value Engine, Night Queue, Morning Brief, Memory/Knowledge Graph, Living Leon UI, and approval/risk controls. The core promise: Leon reliably chooses what matters, routes work correctly, acts autonomously where safe, and presents trusted daily output to the solo owner/operator.

## Primary User
Solo owner/operator using Leon as a personal AI control plane.

## P0 Scope
- Decision Layer + Value Engine hardening.
- Routing evals, score bands, risk gates, agent/tool selection.
- Night Queue + Morning Brief as the first complete end-to-end experience.
- Expanded R1-R5 risk model with examples, rollback, audit trail, and failure modes.

## P1 Scope
- Memory/Knowledge Graph retrieval for context-aware decisions.
- Provenance-aware brief citations and decision explanations.
- Living Leon UI surfaces for review, queue, and approvals.
- Better autonomy throughput and task batching.

## P2/Future Scope
- Richer canvas UI and assistant character.
- Long-running autonomous missions.
- Broader integrations and external actions.
- Full policy/permission system.
- Advanced learning loops from user feedback.

## User Stories

### US-001: Capture User Intent
As a solo operator, I want Leon to understand my request, context, and desired outcome so that it can decide what work is needed.

Priority: P0

Acceptance Criteria:
- Leon classifies requests by intent, urgency, risk, required tools, and expected output.
- Ambiguous requests trigger clarification instead of unsafe execution.
- Classification is logged for inspection.

### US-002: Score Work by Value
As a solo operator, I want Leon to prioritize work by expected value so that the most useful tasks happen first.

Priority: P0

Acceptance Criteria:
- Each candidate task receives a value score with explainable inputs.
- Score bands determine whether work is ignored, queued, proposed, executed, or held for approval.
- The user can inspect why a task was prioritized.

### US-003: Route to the Right Execution Path
As a solo operator, I want Leon to choose the correct route, agent, model, or tool so that work is handled efficiently and correctly.

Priority: P0

Acceptance Criteria:
- Routing decisions use eval-backed criteria.
- Leon can choose between local handling, shell/agent flow, memory retrieval, clarification, or approval.
- Misroutes are captured as evaluation cases.

### US-004: Assign Risk Level Before Action
As a solo operator, I want every action assigned an R1-R5 risk level so that autonomy stays bounded.

Priority: P0

Acceptance Criteria:
- R1-R5 levels include concrete examples.
- R4/R5 actions are always approval-first.
- Risk level, rationale, and approval state are logged.

### US-005: Execute Safe Autonomous Work
As a solo operator, I want Leon to complete low-risk work without interrupting me so that routine work can happen in the background.

Priority: P0

Acceptance Criteria:
- R1-R3 work may execute autonomously according to configured policy.
- Each execution produces status, output, and failure records.
- Failed tasks degrade gracefully and appear in review surfaces.

### US-006: Run the Night Queue
As a solo operator, I want Leon to process queued work overnight so that I start the day with useful progress.

Priority: P0

Acceptance Criteria:
- Night Queue selects tasks using value, urgency, dependencies, and risk.
- Queue execution is resumable and auditable.
- Approval-needed tasks are separated from safe autonomous tasks.

### US-007: Generate the Morning Brief
As a solo operator, I want a concise Morning Brief so that I can review what happened, what matters, and what needs my decision.

Priority: P0

Acceptance Criteria:
- Brief includes completed work, failed work, recommendations, and pending approvals.
- Each item includes enough provenance to trust or inspect it.
- Brief prioritizes actionable output over raw logs.

### US-008: Remember Useful Context
As a solo operator, I want Leon to use memory and knowledge graph context so that decisions improve over time.

Priority: P1

Acceptance Criteria:
- Relevant memories influence prioritization, routing, and brief generation.
- Retrieved context includes provenance.
- User can delete or scrub stored context.

### US-009: Review Decisions and Evidence
As a solo operator, I want to inspect why Leon made a decision so that I can calibrate trust.

Priority: P1

Acceptance Criteria:
- Decision records include inputs, score, route, risk level, and outcome.
- Morning Brief items link back to decision evidence.
- User feedback can mark decisions as useful, wrong, risky, or low-value.

### US-010: Approve High-Risk Actions
As a solo operator, I want a clear approval flow for R4/R5 actions so that Leon can prepare work without crossing boundaries.

Priority: P0

Acceptance Criteria:
- R4/R5 actions remain pending until explicitly approved.
- Approval request shows expected change, risk, rollback plan, and failure mode.
- Rejected actions are logged and not retried without a changed plan.

### US-011: Roll Back or Recover
As a solo operator, I want rollback and recovery paths so that mistakes are contained.

Priority: P0

Acceptance Criteria:
- Risky actions define rollback expectations before approval.
- Failed autonomous tasks record recovery suggestions.
- Leon never hides partial failure from the user.

### US-012: Improve from Evaluation Feedback
As a solo operator, I want Leon’s routing and prioritization to improve from evals and feedback so that Phase 3 becomes more reliable over time.

Priority: P1

Acceptance Criteria:
- Routing failures can become eval cases.
- Eval results are tracked across releases.
- Decision logic changes show impact on routing quality and safety.

## Success Metrics
- Routing quality meets target eval thresholds.
- Morning Brief consistently produces actionable, accurate, prioritized output.
- R4/R5 actions always require approval and produce audit records.
- User can inspect why Leon chose a route, task, or recommendation.
- Night Queue failures are visible, recoverable, and do not block the full brief.

## Open Questions
- Exact numeric thresholds for value score bands.
- Final R1-R5 examples per tool/action category.
- Whether Morning Brief is scheduled only or also generated on demand.
- Whether approvals should live first in dashboard, TUI, or both.

## Release Recommendation
Ship Phase 3 as a reliability-first product layer: harden Decision Layer and Value Engine, connect them to Night Queue execution, then make Morning Brief the daily proof that Leon is choosing, acting, and reporting correctly.