# Leon AI Assistant PRD

## 1. Product Summary

Leon is a local-first personal AI assistant designed to become a living, intelligent operating environment for its owner. It is not a standard chatbot or SaaS dashboard. Leon combines chat, research, memory, workflows, projects, tools, approvals, and autonomous execution into one coherent command center.

The current project foundation/control-plane is treated as existing work and must not be rebuilt unnecessarily. Future development should reuse the existing architecture, tests, governance layer, audit system, task model, approval model, memory MVP, and tool candidate registry wherever practical.

## 2. Primary User

The primary user is the owner/operator of the system: a technical power user who wants a personal AI assistant that can research, plan, automate, and act across digital workflows.

Leon is optimized first for one person, not teams or general consumers.

## 3. Product Vision

Leon should feel like a calm, premium, intelligent digital environment that grows with the user. The assistant should be visibly present, context-aware, and able to act autonomously unless a defined policy blocks the action.

The experience should feel approximately:

- 40% AI-native
- 40% Arc Browser
- 20% Apple

Leon should feel modern, human, quiet, adaptive, and alive without becoming game-like or overly futuristic.

## 4. Current State

The project is currently at a “foundation/control-plane nearly ready” stage, not a finished Leon assistant.

Already completed or assumed available:

- Phase/task/governance planning from existing docs
- Local dashboard/control-plane server
- Approval system
- Audit log and hash-chain validation
- Environment/API key intake flow
- Model routing foundation
- Agent orchestration foundation with mock/dry-run support
- Memory/knowledge graph MVP
- UI composition foundation
- Tool/MCP candidate registry
- Planner proof of concept
- Existing validation suite with passing tests
- Registered GitHub/tool candidates including OpenAI Agents SDK, GitHub MCP, LiteLLM, Playwright MCP, Browser Use, Firecrawl, Apify MCP, Ollama, llama.cpp, vLLM, ExLlamaV2, Mem0, Graphiti, and Cognee

The dashboard should not be used as a progress-update mechanism going forward unless explicitly requested.

## 5. Phase 1 Goal

Phase 1 should deliver the first real Leon product experience: a complete command center foundation where Leon feels like one assistant across chat, research, memory, tasks, workflows, projects, tools, and approvals.

The highest priority is safe autonomy and tool usage. Research/copilot should be the first workflow that feels genuinely useful.

## 6. Phase 1 Scope

Phase 1 includes:

- Local-first operation on the user’s machine/server
- Command center UI with Home, Chat, Workflows, Memory, Skills, Projects, and Settings
- Research/copilot workflow using browser/research tooling where approved
- Mail, calendar, files, and task integration planning and initial gated activation
- Autonomy policy engine
- Approval and audit flow for blocked or high-risk actions
- Missing Component Protocol
- Tool/repository reuse evaluation before building custom functionality
- Existing control-plane/foundation reuse
- Memory and context surfacing inside the assistant experience

Tailscale is not required for Phase 1, though the architecture may remain compatible with it.

## 7. Non-Goals

Phase 1 does not include:

- Voice input/output
- Public deployment
- Team/multi-user productization
- Full mobile-native experience
- Unreviewed handling of secrets
- Autonomous financial actions
- Autonomous public exposure
- Autonomous external account creation
- Autonomous irreversible destructive actions
- Rebuilding existing foundation/control-plane work without cause

## User Stories

### us-001: Open Leon command center

As the owner, I want to open Leon as one coherent command center so that chat, research, memory, workflows, projects, skills, settings, approvals, and status all feel like one assistant instead of disconnected tools.

Acceptance criteria:

- Home, Chat, Workflows, Memory, Skills, Projects, and Settings are available as connected spaces.
- The main experience uses a modular canvas instead of a traditional fixed-sidebar dashboard.
- Leon shows the current assistant state through presence, status color, and activity indicators.

### us-002: Use research copilot

As the owner, I want Leon to research a topic across approved browser/research tools so that I can get useful comparisons, summaries, recommendations, and next-step proposals with less manual effort.

Acceptance criteria:

- Leon can search, browse, compare sources, summarize findings, and track assumptions.
- Leon can turn research output into tasks, plans, drafts, or memory candidates.
- Source references are included where available.
- Tool use follows the configured permission and sandbox model.

### us-003: Let Leon act autonomously when policy allows

As the owner, I want Leon to perform low-risk allowed actions autonomously so that routine work can move forward without asking for approval every time.

Acceptance criteria:

- Leon checks actions against the autonomy policy before execution.
- Allowed low-risk actions can run without blocking for approval.
- Important actions are recorded in the audit log.
- Leon explains meaningful actions and why they were taken.

### us-004: Require approval for high-risk actions

As the owner, I want Leon to stop and request approval for high-risk actions so that money, security, accounts, secrets, public exposure, and irreversible operations remain under my control.

Acceptance criteria:

- Money, purchases, installs, external account changes, public exposure, secrets, security-sensitive permission changes, and irreversible destructive operations always require approval.
- Approval requests clearly describe the action, risk, expected effect, and available fallback.
- Rejected actions are not executed.
- Approval decisions are recorded in the audit log.

### us-005: Use memory safely

As the owner, I want Leon to remember useful context safely so that it becomes more personal and helpful without storing sensitive information unexpectedly.

Acceptance criteria:

- Leon creates candidate memories before durable storage where appropriate.
- Sensitive or credential-like data is blocked from memory.
- The owner can review, delete, and scrub memory.
- Relevant memory can surface in chat, research, and planning.

### us-006: Compose UI from existing components

As the owner, I want Leon to assemble the interface from predefined components so that the UI can adapt to the task while remaining stable, premium, and understandable.

Acceptance criteria:

- Leon uses existing cards, panels, timelines, workflow nodes, graphs, inspectors, memory views, action blocks, lists, media blocks, and tool blocks.
- Leon does not generate a completely new UI for every interaction.
- Components can appear, move, resize, expand, merge, or split with functional animation.
- The interface normally emphasizes one to three important items at a time.

### us-007: Handle missing components and tools

As the owner, I want Leon to handle missing components or tools gracefully so that work does not stop when the perfect building block is unavailable.

Acceptance criteria:

- Leon first evaluates GitHub repositories, MCP servers, SDKs, or maintained tools before custom building.
- Leon uses the best available fallback when a needed component or tool is missing.
- Leon creates a task proposal for missing components or tools when needed.
- Missing functionality is visible as a tracked proposal instead of silently failing.

### us-008: Manage integrations with permissions

As the owner, I want Leon to connect browser/research, mail, calendar, files, and task tools through explicit permissions so that integrations can become useful without unsafe access.

Acceptance criteria:

- Each integration has clear read/write permission boundaries.
- High-risk integration actions are routed through approval.
- Integration actions are auditable.
- Initial activation favors browser/research, then mail, calendar, files, and tasks.

### us-009: Preserve local-first operation

As the owner, I want Leon to run locally first so that the assistant remains under my control while still leaving room for later remote access.

Acceptance criteria:

- Phase 1 runs on the owner’s local machine or server.
- Tailscale is not required for Phase 1.
- Public deployment is out of scope unless explicitly approved later.
- Local-first operation remains compatible with future remote access hardening.

### us-010: Keep technical artifacts in English and chat in Dutch

As the owner, I want Leon to use Dutch for user-facing conversation and English for technical artifacts so that the assistant feels natural while the project remains maintainable.

Acceptance criteria:

- Chat and user-facing conversation default to Dutch.
- Code, architecture notes, structured PRDs, and implementation-facing documentation default to English.
- Leon can adapt language when the owner explicitly asks.

## 8. UX Requirements

Leon’s UI must be a modular canvas, not a traditional dashboard with fixed sidebars and dense widgets.

Core spaces:

- Home
- Chat
- Workflows
- Memory
- Skills
- Projects
- Settings

These spaces should feel connected rather than like separate web pages.

The interface should usually focus on one to three important things at a time. Details should appear only when relevant.

Visual style:

- Dark, soft backgrounds
- Subtle gradients and light noise
- Transparent glass-like panels
- Rounded corners
- Soft shadows and blur
- Generous whitespace
- Minimal visible borders
- One dynamic accent color

Status colors:

- Blue: idle/resting
- Purple: thinking
- Cyan: acting/executing
- Amber: needs attention
- Red: real error or danger only

## 9. Leon Presence

Leon should have a small recognizable digital presence or entity.

It should be:

- Minimal
- Friendly
- Soft 2D/3D hybrid
- Not realistically human
- Subtly glowing

States:

- Idle: calm floating/breathing
- Thinking: focused glow and subtle particles
- Acting: moves toward the component being worked on
- Interacting: visually manipulates or activates components
- Sleeping: dimmed and almost still

Leon’s presence is functional, not decorative. It should help the user understand what Leon is doing and where attention is needed.

## 10. Interaction Model

Leon should respond to intent, not only clicks.

The UI should be assembled from predefined components such as:

- Cards
- Panels
- Timelines
- Workflow nodes
- Graphs
- Inspectors
- Memory views
- Action blocks
- Lists
- Media blocks
- Tool blocks

Leon may choose which components to show, where they appear, how large they are, and what information gets priority.

Leon must not generate an entirely new UI every time. It should compose from existing designed components.

If a needed component/tool does not exist, Leon should first evaluate GitHub/tool reuse, then use the best available fallback or create a task proposal.

## 11. Navigation

Navigation should use a floating transparent dock inspired by Arc and Apple.

The dock should include primary spaces such as:

- Home
- Chat
- Workflows
- Memory
- Settings

The dock may adapt to context, expand temporarily, and react subtly to hover, focus, and Leon activity.

There should be no traditional permanent sidebar in the main experience.

## 12. Animation Requirements

Animations must be functional and communicate state.

The UI should:

- Morph smoothly
- Use spring/physics-based transitions
- Avoid hard page changes
- Let cards expand from their current position
- Let panels merge or split
- Let elements move magnetically toward logical positions
- Preserve visual continuity during changes

Example: a research result card can expand into a full detail workspace without disappearing and remounting as a disconnected page.

## 13. Autonomy And Safety

Leon should be ambitious by default: it may act autonomously unless a policy explicitly blocks the action.

High-risk actions must always require approval.

Always-approval categories:

- Money or purchases
- Installing software or packages
- Creating or modifying external accounts
- Public exposure or publishing
- Secrets/API keys/credentials
- Security-sensitive permission changes
- Irreversible destructive operations

For external actions such as email, calendar, and files:

- Low-risk actions may be autonomous when policy allows
- Public, financial, account/security, or irreversible actions require approval
- Audit logging is mandatory
- Undo or rollback should be available where technically possible
- Leon should explain what it did and why when actions matter

## 14. Research/Copilot Workflow

Research/copilot is the first workflow that should feel magical.

Leon should be able to:

- Search and browse using approved browser/research tools
- Compare sources
- Summarize findings
- Track assumptions
- Produce recommendations
- Turn findings into tasks, plans, or drafts
- Cite relevant sources where available
- Store useful reviewed knowledge into memory

Preferred tool candidates include Playwright MCP, Browser Use, Firecrawl, and Apify, subject to approval and sandboxing.

## 15. Integrations

Priority integration areas after foundation:

- Browser/research
- Mail
- Calendar
- Files
- Tasks

Integrations must use explicit permission boundaries, audit logs, and approval gates for high-risk operations.

OpenAI Agents SDK activation requires:

- API key entered through the safe dashboard/env flow
- Explicit approval
- No raw secret exposure

## 16. Memory

Leon should use memory to become more personal and useful over time without becoming unpredictable.

Memory requirements:

- Review-first for sensitive or durable memory
- Candidate memories before permanent storage where appropriate
- Delete and scrub support
- Credential-like data must be blocked
- Memory should surface naturally in chat, research, and planning
- Future RAG/document ingestion should build on the existing MVP

## 17. Reuse Policy

Before building custom functionality, Leon development should evaluate whether an existing GitHub repository, MCP server, SDK, or maintained tool can deliver the feature faster and more reliably.

Evaluation criteria:

- Active maintenance
- Clear license
- Security posture
- Integration complexity
- Local-first compatibility
- Fit with approval/audit architecture
- Faster path to usable value

Reuse is preferred when it is clearly faster and safer than building from scratch.

## 18. Language

Leon should use Dutch in chat and user-facing conversation by default.

Technical artifacts, code, internal architecture notes, structured PRDs, and implementation-facing documentation should use English unless the user asks otherwise.

## 19. Success Metrics

Phase 1 is successful when:

- Leon feels like one coherent assistant, not disconnected tools
- The user can use chat, research, memory, workflows, projects, skills, settings, and approvals in one command center
- Research/copilot produces useful outputs with less manual effort
- Leon can safely perform allowed autonomous actions
- High-risk actions are blocked or routed through approval
- Audit logs clearly explain important actions
- Existing foundation work is reused instead of duplicated
- Missing components/tools become tracked proposals instead of dead ends

## 20. Key Risks

Risks:

- Overbuilding visual polish before core autonomy works
- Rebuilding existing foundation work
- Unsafe autonomy around external actions
- Too many integrations before permission boundaries are solid
- UI becoming decorative instead of useful
- Memory becoming noisy or storing sensitive information
- GitHub/tool reuse introducing unreliable dependencies

Mitigations:

- Keep Phase 1 focused on command center + safe autonomy + research/copilot
- Reuse existing foundation
- Gate high-risk actions
- Require audit logs
- Evaluate tools before adoption
- Keep Missing Component Protocol active
- Keep voice, public deployment, and team features out of Phase 1

## 21. Phase 1 Deliverable

The Phase 1 deliverable is a local-first Leon command center that combines:

- Living AI-native UI shell
- Floating dock navigation
- Leon presence/status system
- Chat
- Research/copilot workspace
- Memory views
- Workflow/task surfaces
- Project context
- Skills/tools surface
- Settings and permissions
- Approval/audit flow
- Missing Component Protocol
- Safe autonomy policy layer

The product should demonstrate that Leon can research, reason, remember, propose, and act as one assistant while preserving user control over important or risky actions.
