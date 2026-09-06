# Leon product shell and visual system

Status: implemented foundation  
Story: US-001

## Product shell

Leon opens as a working personal AI environment, not as a marketing page, chatbot, admin panel or classic SaaS dashboard.

The first screen must present:

- Leon presence tied to current status.
- A modular canvas with one to three priority surfaces.
- Current status, next action and attention signals.
- A lightweight bottom floating dock for connected spaces.
- Supporting control-plane inspection only below the primary environment.

The main direction explicitly avoids:

- Standard chatbot layout as the default product shell.
- Dense SaaS dashboard grids as the first impression.
- Permanent traditional sidebar navigation.
- Marketing landing pages before the working environment.
- Decorative motion that does not communicate state.

## Visual system

The visual contract is stored in `config/ui-composition.json` under `product_shell.visual_design_rules`.

Rules cover:

- Dark soft backgrounds.
- Subtle gradients or noise.
- Glass panels.
- Rounded corners.
- Blur.
- Glow.
- Shadow.
- Whitespace.
- Minimal borders.
- One dynamic accent color.

The dynamic accent is exposed as CSS variable `--accent` and follows assistant state.

## Status colors

The status-color map is stored in `product_shell.status_colors`:

- `idle`: blue, for calm availability and rest.
- `thinking`: purple, for routing, planning and proposal preparation.
- `acting`: cyan, for approved execution or active local work.
- `attention`: amber, for approvals, missing input, risk review or blockers.
- `error`: red, for real failure, danger or policy violation only.
