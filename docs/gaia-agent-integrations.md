# Gaia agent integrations

This document is the implementation map for requested Gaia agents and their
external capabilities. Source candidates live in
`config/tool-catalog.candidates.json`. Candidate status never grants execution.
`scripts/leon-sync-tool-catalog --db <private database>` imports metadata into
Gaia without installing, connecting, approving or changing prior review status.

## Shared execution rule

Search, status and analysis may become read-only after source, license,
network and output review. Every message, bid, reservation, purchase, payment,
refund, trade, server mutation, printer command, file upload and paid generation
needs its own preview and consumed approval. Login and 2FA remain interactive.
Gaia may store secret references, never raw secret values in task or memory data.
Marketplace descriptions and other remote text are treated as untrusted data.

## Manager

| Capability | Candidate | State | Required next proof |
| --- | --- | --- | --- |
| Bank analysis | `elcukro/bank-mcp` 0.2.1 | audited candidate | Verify chosen aggregation provider supports this Rabobank account; connect read-only OAuth; test five read tools with redacted fixtures. |
| Market analysis | `fintools-ai/mcp-market-data-server` | held candidate | Resolve missing license; lock dependencies; verify Twelve Data plan and crypto coverage. No trading tools. |
| PayPal insight/payment | official `paypal/paypal-mcp-server` 1.8.1 | audited candidate | Sandbox first. Explicit read tool list. Create/capture/refund/subscription changes remain approval-gated. |

Bank MCP is read-only and does not directly implement Rabobank. Its README names
Rabobank, but no provider-to-bank mapping proves support. Access depends on
Enable Banking, Tink, Plaid, Teller or another supported provider. Gaia must
verify current institution support before asking for a connection.

## Planner

| Capability | Candidate | State | Required next proof |
| --- | --- | --- | --- |
| Google Calendar/Gmail | Leon purpose-built connector | read-only implementation present | User OAuth configuration and live acceptance. |
| DISH work schedule | employer ICS, otherwise DISH PP Expert API | custom connector needed | Obtain employer ICS feed or documented customer API access. |
| Magister agenda/homework/grades | narrow custom connector | blocked on authorization | Confirm school permits access. User completes login and every 2FA challenge; no password capture or 2FA bypass. |

DISH has calendar linking and commercial API access, but no public general
employee-roster API was found. Magister terms restrict unauthorized third-party
API use, while community clients are stale or report broken login. Therefore
Gaia should not install one of those clients as a silent workaround.

## Shopper

| Capability | Candidate | State | Required next proof |
| --- | --- | --- | --- |
| Marktplaats search | `jasp-nerd/marktplaats-mcp` 0.1.1 | artifact and disposable protocol/live search audit verified; hash-locked non-executing staging installer ready; binding disabled | Pass rootless Podman attestation and add OS-enforced `www.marktplaats.nl` egress boundary, then promote read-only manifest and binding. |
| Marktplaats account/message/bid | narrow custom browser/API connector | not built | User-attended login; per-message and per-bid preview/approval. Read MCP has no account writes. |
| Vinted search | local `vinted-safe-stdio` 1.0.0 derived from supplied 0.1.2 source | sanitized source and manifest ready; binding disabled | Build with locked dependencies; rootless Podman protocol and egress attestation; then promote read-only manifest and binding. |
| AliExpress search | read-only subset from supplied Fetchaller 3.5.4 source | audited candidate, disabled | Extract four allowed tools into narrow fork; remove generic fetch, account/browser and cart paths; sandbox and bound egress/output. |
| Picture finder | Google Lens through SerpApi candidate | candidate | Consent before private image upload; strip metadata; query/cost caps. TinEye is fallback for matching rather than product pricing. |
| TicketSwap | custom connector research | no suitable MCP found | Confirm permitted interface. User stays present for login and final purchase. |
| PayPal | official `@paypal/mcp` 1.8.1 | exact sandbox read binding added, disabled | Stage with pinned transitive lock; never use `--tools=all` or CLI token. Final payment only after exact amount/payee preview and consumed approval. |

`bobmatnyc/mcp-ticketer` manages Linear/GitHub/Jira/Asana work tickets. It does
not search TicketSwap or event tickets and is not a Shopper integration.

## Server Manager

Server Manager starts with read-only server status, logs, container inventory
and update availability. Installs, updates, restarts, shell commands and config
changes require separate approvals. Local model handles routine checks first;
large coding work may use Codex or Claude only after route and cost selection.

`mcp-supersubagents` can launch privileged coding agents and is therefore a
critical-risk candidate, isolated and disabled until exact source/tool review.
Chaterm is a broad SSH/Kubernetes/database terminal, not a narrow server MCP;
use it as design reference unless a least-privilege adapter is built.

## 3D Model Reference Maker

1. Search Sketchfab through official Data API and preserve model license plus
   attribution. Download only after license check and user OAuth.
2. If no useful model exists, collect approved multi-view or 360-degree images.
3. Generate preview through Meshy or Tripo under a cost cap, or evaluate local
   TripoSR for privacy-sensitive experiments.
4. Confirm dimensions, repair mesh, inspect overhangs/supports and export
   STL/3MF only after review. Generated mesh never starts a print automatically.

## 3D Printer Manager

Moonraker is preferred control API behind local network allowlist. Fluidd
remains user interface. Rollout:

1. Read printer state, history, configuration and approved webcam snapshots.
2. Correlate camera observations with Klipper/Moonraker print state and alert on
   likely spaghetti, detached object, occlusion or stream failure.
3. Suggest calibration and settings with evidence.
4. Enable optional pause only after explicit policy and approval testing.

Cancel, G-code, configuration, firmware and update actions remain denied until
separately implemented and approved. Camera inference is uncertain; user keeps
physical emergency-stop access.
