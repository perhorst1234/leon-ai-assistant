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
- `marktplaats_read_own_messages`: bounded owner messages from the currently
  open conversation, excluding payment cards; fixed DOM-only extraction.
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

## Owner login on macOS, browser connection to the VM

On the owner's Mac, run this in Terminal to open a separate Chrome profile:

```sh
open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/Library/Application Support/LeonShopperChrome"
```

Log into Marktplaats, Vinted, TicketSwap and Ticketmaster in that window.
In another Terminal tab, create the loopback-only SSH tunnel to the Leon VM:

```sh
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 127.0.0.1:9222:127.0.0.1:9222 per@192.168.178.177
```

SSH may ask for the VM user's password and first-time host-key verification.
An idle Terminal after login is expected: it keeps the tunnel open. Keep that
tab and the separate Chrome window open. Closing the tunnel disconnects the
MCP server's browser access. This requires Google Chrome; Safari cannot expose
the Chrome DevTools Protocol endpoint used by this connector.

The server address was checked on the VM as `192.168.178.177`. Chrome login
and the tunnel still require acceptance from the owner's Mac.

## Windows alternative

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
Initially no real marketplace account was logged in or messaged. That smoke had a
temporary-profile cleanup race and a fixture quoting issue; the corrected test
with process-tree cleanup passed.

On 26 September the owner connected Chrome on macOS over the loopback SSH
tunnel. CDP and the logged-in Marktplaats page were verified; 24 owner messages
from four purchase conversations were read. Only a compact tone/strategy
profile was saved in private local state, outside this public repository.
No external message or purchase was performed. Vinted, TicketSwap and
Ticketmaster login status was not verified. The live Marktplaats composer
uses the exact label `Sturen`, now supported by the send guard. Interactive
snapshots are used for send refs; output is capped before returning it.

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
