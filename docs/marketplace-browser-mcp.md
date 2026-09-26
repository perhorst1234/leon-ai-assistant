# Marketplace browser MCP

The user authorized access to their own marketplace accounts and ordinary
messages without a per-message approval. This connector implements that grant
as an explicit server capability (`--allow-messages`). Passwords are not an
MCP argument. The owner signs into a dedicated Chrome profile themselves.
This is a browser connector, not OAuth and not a public marketplace API.

## Current capabilities

- `marketplace_capabilities`: configuration status, no cookies or tokens.
- `marketplace_open`: supported HTTPS listings/conversations, no checkout URLs.
- `marketplace_read_page`: visible page snapshot, including conversation text.
- `marketplace_send_message`: Marktplaats/Vinted only, enabled by startup grant;
  exact current conversation URL, message textbox and explicit Send button.

Browser content remains untrusted. Private messages must remain local and must
not be committed or sent to cloud models as tone-training input. The MCP server
does not itself attach to Leon's text-only model runtime. Wiring the agent to
these tools and the weekly scheduler is a remaining integration step.

There are no bid, like, reservation, checkout or purchase tools in this version.
TicketSwap and Ticketmaster support page reads only. Website login challenges
and Google/2FA must be completed by the owner, never bypassed. Account/site
compatibility needs a live acceptance test after the owner signs in. A passing
DOM test is not evidence that an account is connected.

## Owner login on Windows, browser connection to the VM

Start a **separate** Chrome profile on the Windows computer (PowerShell):

```powershell
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:LOCALAPPDATA\LeonShopperChrome"
```

Log into the relevant websites in that window. Forward only the local debugging
port to the VM with SSH; do not expose it on the LAN or internet:

```powershell
ssh -N -o ExitOnForwardFailure=yes -R 127.0.0.1:9222:127.0.0.1:9222 per@192.168.178.177
```

Leave Chrome and SSH running. On the VM, start the stdio MCP server:

```sh
cd /home/per/leon-ai-assistant
.venv/bin/python -m leon_control_plane.marketplace_browser_mcp --allow-messages
```

MCP clients must launch that command through stdio; it is not an HTTP service.
Omit `--allow-messages` for read-only access. `--agent-browser` overrides CLI
discovery; this server reuses cached agent-browser 0.27.0 without downloading.

## Verification and limits

Protocol/authorization, host restrictions, checkout-path rejection, current
conversation/ref checks and durable duplicate/uncertain-send blocking are tested.
A real disposable Chromium/CDP test on the VM read textbox and Send-button refs
and filled/clicked a message on a local test page. Twenty focused tests pass,
including MCP stdio negotiation for the message-enabled server.
No real marketplace account was logged in or messaged. That smoke had a
temporary-profile cleanup race and a fixture quoting issue; the corrected test
with process-tree cleanup passed.

Send attempts are hashed and persisted before clicking, with a 60-second global
rate limit. Metadata audit stores no message text or conversation URL. A click
is not delivery confirmation. On a timeout, status is unknown and the same
message cannot be retried automatically, including after a server restart.
Changing the message is not permission to resend an uncertain attempt.

This is intended for the owner's dedicated browser with a single controller.
Do not use Chrome manually during a send: CDP cannot atomically prevent the
owner changing tabs during a browser operation. Website DOM/labels may change;
unsupported labels fail instead of selecting a generic button. Host checks
apply to top-level tool navigation, not every request made by the browser.
