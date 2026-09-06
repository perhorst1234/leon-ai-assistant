# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated: React 19 with TypeScript, Vinext/Vite and Tailwind CSS via the OpenAI Sites scaffold. This was selected because the user asked for a polished, portable frontend and left the implementation stack open.

## Users

The primary user is Per, using Gaia throughout the day as a personal AI companion and operating layer. He wants to move between conversation, workflows, memory and settings without losing the sense that he is interacting with one continuous assistant.

## Product Purpose

Gaia makes a personal AI feel present rather than boxed inside a chatbot. The product combines conversation, contextual interfaces, memory spaces and visible tool activity into one living canvas. Success means the user can understand what Gaia is doing, ask or trigger an action quickly, and feel that the same companion follows them through every part of the product.

## Positioning

Gaia's distinctive mechanism is a persistent visual companion that moves through and manipulates a composable interface: it can be dragged toward UI zones, changes state while thinking or acting, and turns responses into useful spatial components instead of a plain message stream.

## Operating Context

The experience centers on four connected spaces: Today, Chat, Workflows and Memory, with contextual settings available from the same floating navigation. Gaia may combine tools, reflect on work, learn preferences, suggest useful next steps and visualize background activity. The current deliverable is a high-fidelity frontend prototype with realistic synthetic data.

## Capabilities and Constraints

- The frontend must be complete, responsive, interactive and suitable for later backend integration.
- Backend calls, persistence, tool execution and AI reasoning are mocked for this version.
- Gaia needs recognizable idle, listening, thinking, acting and resting states.
- Navigation is a floating, frosted tab island rather than a conventional sidebar.
- The assistant remains present across spaces and supports a drag-to-command interaction model.
- Interfaces are composed from reusable cards, timelines, controls and tool views rather than ad-hoc generated HTML.
- Expensive or irreversible actions must remain previews until a real backend and confirmation model exist.

## Brand Commitments

The product name is Gaia. It must feel like a calm, intelligent, living companion rather than a game character, generic SaaS dashboard or ChatGPT clone. Binding references from the user are Apple material quality and physicality, Arc's fluid playfulness, AI-native adaptive UI, Daylight's calm product presentation, Apple's frosted tab-switch bubble and an organic breathing animated grid. The intended balance is 40% AI-native, 40% Arc and 20% Apple.

## Evidence on Hand

The linked design conversation contains confirmed product and interaction preferences. No production backend, customer claims, usage metrics, testimonials or final character artwork were provided. All example tasks, memories, calendar events and tool results in the prototype must therefore be treated as synthetic demonstration content.

## Product Principles

1. Presence over chat chrome: Gaia should always feel like one entity inhabiting the interface.
2. Show the work beautifully: tool use, reasoning state and workflows become legible visual experiences.
3. Calm first, delight through behavior: motion and personality must clarify the experience rather than compete with it.
4. Continuity over page changes: spaces morph, shared elements persist and context is never abruptly discarded.
5. User agency remains visible: initiative is useful and reversible, never mysterious or controlling.

## Accessibility & Inclusion

Keyboard, touch and pointer interactions must all remain usable. Motion, transparency and contrast preferences are respected; reduced-motion users receive short crossfades and static state cues instead of spatial movement. Interactive targets should be at least 44 by 44 CSS pixels on touch layouts.
