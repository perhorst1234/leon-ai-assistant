---
name: Gaia
description: A living AI companion and spatial mission-control observatory.
colors:
  nocturnal-cobalt-black: "#07080f"
  porcelain-ink: "#f7f8ff"
  pearl-violet: "#a795ff"
  signal-cyan: "#8fe9ff"
  memory-mint: "#b8f7dc"
  panel-matte: "rgba(20, 22, 34, 0.68)"
  command-panel: "rgba(15, 17, 27, 0.76)"
  action-pearl: "#d8d2ff"
  action-cyan: "#a7e7ef"
  command-pearl: "#ece9ff"
  approval-amber: "#f3ddb0"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "clamp(2.15rem, 3.5vw, 4.2rem)"
    fontWeight: 560
    lineHeight: 0.98
    letterSpacing: "-0.038em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "clamp(1.8rem, 2.45vw, 2.65rem)"
    fontWeight: 540
    lineHeight: 1.02
    letterSpacing: "-0.036em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "17px"
    fontWeight: 620
    lineHeight: 1.2
    letterSpacing: "-0.018em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', var(--font-geist-sans), Arial, Helvetica, sans-serif"
    fontSize: "11px"
    fontWeight: 560
    lineHeight: 1.35
    letterSpacing: "0.04em"
  mono:
    fontFamily: "var(--font-geist-mono), monospace"
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "normal"
rounded:
  xs: "7px"
  sm: "12px"
  control: "14px"
  node: "15px"
  panel: "16px"
  island: "20px"
  sheet: "22px"
  pill: "999px"
  circle: "50%"
  organic: "48% 52% 45% 55% / 42% 44% 56% 58%"
spacing:
  2xs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  2xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.command-pearl}"
    textColor: "{colors.nocturnal-cobalt-black}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 15px"
    height: "44px"
  button-quiet:
    backgroundColor: "rgba(255, 255, 255, 0.06)"
    textColor: "{colors.porcelain-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 15px"
    height: "44px"
  navigation-frost:
    backgroundColor: "rgba(24, 26, 38, 0.52)"
    textColor: "{colors.porcelain-ink}"
    rounded: "{rounded.island}"
    padding: "5px"
    height: "52px"
  input-prompt:
    backgroundColor: "rgba(22, 24, 36, 0.70)"
    textColor: "{colors.porcelain-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sheet}"
    padding: "7px"
    height: "62px"
  command-dock:
    backgroundColor: "rgba(21, 23, 34, 0.68)"
    textColor: "{colors.porcelain-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.island}"
    padding: "6px 7px 6px 15px"
    height: "58px"
  card-matte:
    backgroundColor: "{colors.panel-matte}"
    textColor: "{colors.porcelain-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.panel}"
    padding: "18px"
  card-mission:
    backgroundColor: "{colors.command-panel}"
    textColor: "{colors.porcelain-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.panel}"
    padding: "24px"
  review-sheet:
    backgroundColor: "rgba(18, 20, 30, 0.94)"
    textColor: "{colors.porcelain-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sheet}"
    padding: "22px"
    width: "520px"
  agent-option:
    backgroundColor: "rgba(255, 255, 255, 0.045)"
    textColor: "{colors.porcelain-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.node}"
    padding: "12px"
    height: "132px"
  memory-node:
    backgroundColor: "rgba(23, 26, 39, 0.76)"
    textColor: "{colors.porcelain-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.circle}"
    size: "80px"
  companion-entity:
    backgroundColor: "{colors.pearl-violet}"
    textColor: "{colors.memory-mint}"
    rounded: "{rounded.organic}"
    width: "154px"
    height: "174px"
---

# Design System: Gaia

## Overview

**Creative North Star: "The Living Companion Observatory"**

Gaia is a living companion and a mission-control surface for autonomous work. The authored world is the spatial companion observatory from direction 7, grounded by seed `4fb3b735`: a nocturnal cobalt-black field inhabited by one persistent pearl-violet entity, a breathing orthogonal lattice, and sparse mint/cyan signals. It deliberately refuses both the generic AI transcript and the dense admin dashboard.

The visual language combines Apple-like continuous geometry and material restraint with an AI-native spatial composition. Frost belongs to navigation, command, and transient review islands; durable information remains matte and legible. Today opens as a personal command center, then branches into fundamentally distinct Chat, Work, and Memory spaces while Gaia preserves continuity between them.

The first viewport must show Gaia fully visible in the open center. One active mission and two attention requests orbit the companion, while a compact command dock sits outside Chat. In Chat, that dock becomes the full prompt island. The result should feel calm, intelligent, alive, premium, and reassuring—not gamified or administratively dense.

**Final reviewer disposition:** Ship. All listed finish-review fixes are resolved in the documented implementation.

**Key Characteristics:**

- Persistent pearl-violet Gaia entity in an open spatial center
- Apple-style frosted segmented navigation bubble
- Today command center with one mission and two attention requests
- Long-work cockpit with visible progress, ETA, checkpoints, agents, approvals, and resume state
- Breathing orthogonal lattice with sparse violet, cyan, and mint state signals
- Matte operational surfaces with frost reserved for command islands

## Colors

The palette uses rare luminous signals over a nearly black cobalt field; the frontmatter values are normative.

### Primary

- **Pearl Violet:** Gaia’s identity, selected navigation, memory emphasis, and companion light.
- **Action Pearl / Command Pearl:** Positive or initiating actions. Command Pearl is the solid high-clarity action used by mission and review controls; Action Pearl is the first stop in the Chat send gradient.

### Secondary

- **Signal Cyan / Action Cyan:** Active tool work, progress, focus, and the second stop of the Chat action gradient.

### Tertiary

- **Memory Mint:** Listening, successful completion, durable memory, and reversible confirmation.
- **Approval Amber:** Attention that requires Per’s explicit decision before an external or consequential action.

### Neutral

- **Nocturnal Cobalt Black:** Continuous canvas and browser theme.
- **Porcelain Ink:** Primary text and high-contrast iconography; secondary text uses controlled alpha.
- **Panel Matte:** General semantic cards and inspectors.
- **Command Panel:** Today mission, Work cockpit, attention, approval, and resilience surfaces.

### Named Rules

**The Rare Signal Rule.** Pearl Violet identifies Gaia and selection; Signal Cyan indicates active work; Memory Mint confirms listening, memory, and completion; Approval Amber marks a decision gate. Keep each signal scarce against the cobalt field.

**The Truth Color Rule.** Amber never implies that an external action already happened. Pair it with explicit approval language, an example label, or a “nothing executed” statement.

## Typography

**Display Font:** the native Apple/system UI stack, with Geist Sans and Arial/Helvetica fallbacks  
**Body Font:** the same native Apple/system UI stack  
**Label/Mono Font:** the system stack for labels; Geist Mono for keyboard hints and exact system values

**Character:** The system stack creates an Apple-like, platform-native calm while Geist keeps the experience stable off Apple platforms. Tight large type opens the spatial canvas; operational text stays readable and compact without becoming dashboard microcopy.

### Hierarchy

- **Display** (560, `clamp(2.15rem, 3.5vw, 4.2rem)`, 0.98): Today and Work statements with generous surrounding space.
- **Headline** (540, `clamp(1.8rem, 2.45vw, 2.65rem)`, 1.02): Active mission titles and consequential conversational conclusions.
- **Title** (620, 17px, 1.2): Space headings and panel titles.
- **Body** (400, 13px, 1.5): Operational explanations, mission descriptions, review details, and agent context; prominent operational copy may rise to 14px.
- **Label** (560, 11px, 0.04em): State, type, provenance, ETA, checkpoint, and timeline metadata.
- **Mono** (400, 10px, 1.2): Keyboard hints and exact system values only; it is not body copy.

### Named Rules

**The Operational Floor Rule.** Meaningful operational copy stays within 11–14px with comfortable line-height; only keyboard hints and nonessential prototype stamps may drop to 10px.

**The Quiet Scale Rule.** Large type opens space; operational type explains state. Never use dozens of intermediate sizes to simulate hierarchy.

## Layout

Gaia is a full-viewport spatial canvas with a 320px minimum width and a 640px desktop minimum height. Desktop is deliberately asymmetric: the frosted 52px space switcher crowns the field, the companion owns the open center, and information sits at the periphery instead of filling a dashboard grid. The first viewport places the active mission to the left, two attention requests to the right, and small context signals around—not over—the companion.

Today is the personal command center. Chat is a separate conversational composition and the only space with the full 62px prompt island. Work is a long-mission cockpit: the primary mission console shows the end goal, current phase, progress, expected finish, checkpoints, and pause/resume state; the secondary orbit holds the agent team, approval gate, and resilience log. Memory uses a spatial node graph plus one focused inspector.

Spacing follows a compact 4px base with recurring 8, 12, 16, 20, 24, and 28px steps. At 1100px, navigation labels and side content compress; at 820px, spatial graphs and inspectors tighten; at 700px, the surface becomes vertically scrollable and stacks into a single flow. Mobile preserves a deliberate companion gap before Today’s mission and Work’s cockpit, then places full-width mission, attention, approval, agent, and resilience surfaces below it. Short desktop viewports reduce vertical spread without collapsing the spatial center.

**The Living Center Rule.** Preserve an open central field for Gaia. Peripheral information may orbit or stack around it, but must not box the companion into a card or cover it with a dashboard grid.

**The Distinct Spaces Rule.** Today, Chat, Work, and Memory share one world and one companion, but each has its own task-native composition. Do not reduce them to one transcript with changing side panels.

## Elevation & Depth

The system uses a hybrid of ambient light, matte tonal layering, and restrained frost. Persistent semantic surfaces are matte; navigation, Chat input, command docks, settings, agent selection, and review sheets may use blur because they are active or transient command layers. Gaia alone receives deeply modeled volume and colored ambient light.

### Shadow Vocabulary

- **Operational matte** (`0 24px 76px rgba(0, 0, 0, 0.30), inset 0 1px rgba(255, 255, 255, 0.08)`): Today mission, Work console, attention, agent, approval, and resilience surfaces.
- **Navigation frost** (`0 16px 50px rgba(0, 0, 0, 0.26), inset 0 1px rgba(255, 255, 255, 0.10)`): Persistent space switcher and its segmented active bubble.
- **Command frost** (`0 22px 64px rgba(0, 0, 0, 0.34), inset 0 1px rgba(255, 255, 255, 0.10)`): Compact command dock outside Chat.
- **Prompt frost** (`0 24px 70px rgba(0, 0, 0, 0.35), inset 0 1px rgba(255, 255, 255, 0.11)`): Chat composer and focus response.
- **Review frost** (`0 34px 100px rgba(0, 0, 0, 0.48), inset 0 1px rgba(255, 255, 255, 0.10)`): Approval, learning, and agent-selection sheets.
- **Companion volume** (`0 28px 62px rgba(33, 24, 84, 0.42), inset 14px 16px 32px rgba(255, 255, 255, 0.28), inset -16px -20px 30px rgba(41, 33, 97, 0.34)`): Gaia’s modeled body only.

### Named Rules

**The Reserved Frost Rule.** Apply backdrop blur only to navigation, prompt, compact command, settings, agent-selection, and review islands. Mission data, memory inspectors, and other persistent semantic cards remain matte.

## Shapes

The form language is continuous, softly tactile, and Apple-like without imitating platform chrome literally. Small utility surfaces use 7–12px corners, standard controls use 14px, operational nodes use 15px, persistent panels use 16px, navigation and command islands use 20px, and transient sheets or the Chat prompt use 22px. Pills carry statuses and compact metadata; memory nodes are circular; Gaia keeps its asymmetrical organic silhouette.

**The Continuous Geometry Rule.** A container and the controls nested inside it should share a coherent corner family and optical inset; avoid random radii or hard dashboard rectangles.

**The Soft Geometry Rule.** Use rounded rectangles, pills, and circles. Never sharpen the world into technical admin chrome.

## Components

Components feel softly tactile, magnetic, and restrained. Default control feedback lands in 140–180ms with the strong ease-out curve; spatial relocation is slower and spring-like. Keyboard focus uses a two-pixel cyan ring. Every supported motion has a static or near-instant alternative.

### Buttons

- **Shape:** 14px continuous corners with a 44px minimum hit area.
- **Primary:** Dark ink over Command Pearl for mission, dock, approval, and review acceptance; the Chat send action uses the Action Pearl-to-Action Cyan gradient.
- **Quiet:** Porcelain Ink over a 6% white tonal surface; hover rises to 10% white and press compresses to 96–98% scale.
- **Approval:** Warm amber is reserved for user-gated consequential actions and is always paired with explicit pending-state copy.
- **Hover / Focus:** 140–160ms tactile response and the shared two-pixel Signal Cyan focus ring.

### Navigation

- **Style:** A 52px frosted island with 44px tabs, a 15px active segment, and a 20px outer radius.
- **State:** The active bubble relocates with a 420ms zero-bounce spring. Labels hide below 1100px while icon targets remain 44px.

### Prompt Input and Command Dock

- **Chat prompt:** A 62px frosted island with a transparent 46px input, voice control, keyboard hint, and 44px send control. Listening shifts the material toward Memory Mint without changing geometry.
- **Compact dock:** Outside Chat, a 58px island reports mission or memory status and offers one 44px “Nieuwe opdracht” action. It opens Chat rather than embedding a second composer.

### Mission Console

- **Content contract:** Always expose end goal, current phase, percent complete, ETA or expected finish, checkpoint timeline, and a pause/resume control.
- **Resilience:** Long missions show the latest resumable checkpoint and make a paused mission safe to continue.
- **Density:** The console is the dominant matte surface, while agent, approval, and resilience modules stay smaller and peripheral.

### Agent Team

- **Automatic mode:** Gaia may select a team per phase, but must show why the combination fits task, risk, and available tools.
- **Manual mode:** Per can choose specialists directly; selected cards use a restrained violet fill and explicit selection mark.
- **Permission language:** Each agent states its relevant permission or approval boundary. No team choice bypasses the external-action gate.

### Review Sheet

- **Approval pattern:** Show the proposed action, amount or impact, requesting agent, and the statement that nothing has executed. Offer decline and a clearly labeled example approval.
- **Learning pattern:** Show the proposed learning, why it was suggested, and when it will be reviewed. Accepting schedules or records a proposal; it does not silently install or mutate anything.
- **Behavior:** Approval and learning share one 22px frosted sheet pattern, trapped keyboard focus, Escape dismissal, and stacked mobile actions.

### Matte Cards and Memory Nodes

- **Cards:** Persistent semantic panels use matte surfaces, 16px corners, 16–24px padding, and the operational matte shadow without backdrop blur.
- **Memory nodes:** Circular 70–96px objects use scale for importance and deeper Pearl Violet for selection. One adjacent inspector explains content and provenance.

### Gaia Companion and Lattice

Gaia is a 154px by 174px pearl-violet organic body with dimensional gradients, mint eyes, face inset, feet, orbit lines, and a colored ground shadow. Idle breathing lasts 4.6s; thinking and acting shorten the same motion while state hues shift from violet toward cyan or mint. The orthogonal particle lattice breathes on a slower 7s rhythm, responds to pointer proximity, and adopts the same state palette. Dragging Gaia reveals three magnetic command zones, but clicking also opens equivalent quick actions.

Reduced motion collapses animation and transition durations to near-instant values and leaves static state cues. Reduced transparency replaces frost with solid `#171925`. Increased contrast strengthens secondary text, island borders, and command backgrounds. Mobile retains 44px targets and the reserved companion gap before stacked content.

### Named Rules

**The 44-Pixel Rule.** Every interactive control remains at least 44px tall or wide wherever touch is supported.

**The State Continuity Rule.** Thinking, acting, listening, pausing, and resuming change accent hue, tempo, and status copy while Gaia remains the same entity and the mission retains its checkpoint trail.

**The Approval Gate Rule.** External, financial, installation, server, printer, or other consequential actions remain previews until Per explicitly approves them. Every example flow states what has not happened.

## Do's and Don'ts

### Do:

- Do preserve Gaia as one persistent pearl-violet entity across Today, Chat, Work, and Memory.
- Do keep the first viewport spatial: Gaia visible in the center, one mission and two attention requests orbiting it, and the command dock outside Chat.
- Do expose goal, current phase, progress, ETA, checkpoints, pause/resume state, team rationale, and approval boundaries for long work.
- Do label synthetic content as “voorbeeld” or “voorbeelddata” and state clearly when no external action, payment, installation, or mutation occurred.
- Do use matte surfaces for persistent information and frost only for navigation, command, settings, selection, or review islands.
- Do preserve 11–14px operational type, 44px targets, explicit focus rings, reserved mobile companion space, stacked mobile flow, reduced motion, reduced transparency, and increased-contrast states.

### Don't:

- Don't turn Gaia into a generic SaaS dashboard, dense admin cockpit, or transcript-plus-sidebar chatbot.
- Don't reuse the full Chat composer in Today, Work, or Memory; use the compact command dock there.
- Don't hide long-running work behind a spinner or vague “working” label.
- Don't imply that synthetic data is live or that approval-gated actions already executed.
- Don't apply glass to every card, use neon cyberpunk color, or let glow compete with operational clarity.
- Don't remove the companion on mobile without preserving the deliberate gap and continuity cue in the stacked flow.
