# Leon Phase 2 - Leon Shell, Agent Flow en Modelrouting

## Summary
Phase 2 maakt Leon de enige hoofdinterface. De oude dashboard-home verdwijnt en wordt vervangen door een productwaardige Leon Shell: een rustige AI companion/workspace met actuele task attention, approvals en benchmark-gated local/cloud modelrouting.

## Goals
- Leon-only home screen.
- Oude dashboardervaring verwijderen uit de hoofdervaring.
- Desktop-first 16:9 UI voor 1920x1080 en 2560x1440.
- End-to-end flow: vraag -> proposal -> approval -> uitvoering -> resultaat.
- Tesla M40 24GB gebruiken waar benchmarks slagen.
- API fallback gebruiken waar lokaal te traag of onvoldoende is.
- UI visueel sterk uitwerken, ook als Phase 2 functioneel smal blijft.

## Non-Goals
- Geen implementatie tijdens deze PRD-stap.
- Geen voice, zware memory graph of externe app-integraties in Phase 2.
- Geen lange admin/componentlijst op het home screen.
- Geen GPU-backend, modeldownload of provider-enable zonder aparte approval.

## User Stories

### US-001: Leon-only Home Screen
As a user, I want Leon to open into a calm AI workspace, so that I do not land in a technical dashboard.

Acceptance Criteria:
- Leon is the clear first viewport.
- The old dashboard-home is not visible as the primary experience.
- No long admin/component lists appear on home.

### US-002: Dynamic 16:9 Layout
As a user, I want the Leon interface to work well on 16:9 desktop screens, so that it feels native on my main monitor.

Acceptance Criteria:
- 1920x1080 has no overlap, clipping or layout shifts.
- 2560x1440 has no overlap, clipping or layout shifts.
- Mobile and tablet remain usable.

### US-003: Current Task Attention
As a user, I want only the task that needs attention shown on home, so that Leon does not feel like a project management dashboard.

Acceptance Criteria:
- Home can show current task, approval needed, running, waiting or done.
- Home does not show the full backlog.
- Full task details are available in the Tasks tab.

### US-004: Proposal and Approval Flow
As a user, I want Leon to propose a plan before sensitive actions, so that I stay in control.

Acceptance Criteria:
- Leon can receive a user request.
- Leon can show a plan or proposal.
- Leon asks approval before sensitive or executing actions.
- Leon continues execution only after approval.

### US-005: Local and Cloud Modelrouting
As a user, I want Leon to use the Tesla M40 when it is fast enough and API fallback when it is not, so that the system balances speed, cost and quality.

Acceptance Criteria:
- Modelrouter can choose local or API per task.
- Route decision is visible to the user.
- M40 routes are only enabled after benchmark pass.
- API fallback works when local route fails or is too slow.

### US-006: Hidden Technical Inspect
As a user, I want technical details available but not dominant, so that Leon stays clean while still being controllable.

Acceptance Criteria:
- Settings/Inspect contains technical state where needed.
- Auth, secrets, audit, approvals, task store and routing can remain internally.
- Technical screens do not dominate the home experience.

### US-007: Runtime and Model Reuse Review
As a developer, I want relevant GitHub/runtime options reviewed before custom work, so that Phase 2 reuses strong existing systems where practical.

Acceptance Criteria:
- OpenAI Agents SDK is reviewed for agent runtime.
- llama.cpp is reviewed as first Tesla M40 backend candidate.
- Ollama is reviewed as second local backend candidate.
- LiteLLM is considered later for gateway/sandbox usage.
- Playwright MCP/Browser Use is considered only if controlled-browser work is in scope.

## Functional Requirements
- Navigation contains: Leon, Tasks, Memory, Settings/Inspect.
- Existing Phase 1 menu bar style remains the visual base.
- Leon Shell must feel like an AI companion/workspace, not a chatbot or admin dashboard.
- Agent flow must support request, proposal, approval, execution and result.
- Modelrouting must expose local/cloud choice.
- Backend/control-plane features may remain only where they support Leon.

## Success Metrics
- 0 old-dashboard elements on Leon home.
- 100% primary 16:9 viewport checks pass.
- End-to-end demo flow completes successfully.
- 100% local modelroutes have benchmark evidence.
- Route decision is visible for each agent execution.
- User experience feels product-grade, not prototype-grade.

## Phase 2 MVP Scope
- Leon-only home screen.
- Minimal tabs: Leon, Tasks, Memory, Settings/Inspect.
- Product-grade UI polish.
- Proposal/approval/result flow.
- Visible local/cloud modelrouting.
- Tesla M40 benchmark gates.
- Old dashboard-home removed from the primary experience.

## Future Scope
- Voice.
- Whisper/local speech tests.
- Heavy memory graph.
- External app integrations.
- Broad GitHub catalog scoring.
- Advanced multi-agent workflows.