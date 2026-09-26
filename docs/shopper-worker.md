# Leon shopper worker

Leon owns the search and contact loop. `/shopper` is an authenticated dashboard
for durable Marktplaats/Vinted watches, budget, RAM capacity/slot constraints,
pause/resume and latest real results. API requests use the existing backend
bearer token and web session/same-origin proxy; no browser session is exported.

The user-systemd `leon-shopper-watch.timer` checks due searches hourly. Each enabled watch
searches weekly; disconnected/unsupported search pages retry after one hour.
A persistent headless Chrome runs on the server at loopback CDP port 9223;
no Mac browser or SSH tunnel is needed. Owner-authorized marketplace sessions
were transferred privately; Marktplaats owner login was confirmed on the server.
Only marketplace cookies were moved, without logging values or transferring
Google credentials. The private browser profile stays outside Git. A process lock prevents the timer/backend from controlling the browser
simultaneously. Captchas and login/consent requirements stop the run.

Search reads at most 40 rendered listings, deduplicates public listing URLs and
filters price, text, total RAM and usable slots. Asking prices do not confirm
shipping or compatibility. The owner watch requests DDR3 ECC, minimum 64 GB,
preferred 128 GB, four slots and a maximum total of EUR49.99. CPU compatibility
and actual seller stock must still be verified before buying.

With automatic messages enabled, Leon's local Ollama model on the M40 selects
one of at most three real candidates and a bounded offer. It cannot invent
URLs or tools; the code validates budget/index and composes a short friendly
message from the private coarse tone profile. The 89C preflight prevents a hot
GPU from starting this reasoning call. No OpenAI calls are used by this worker.

Marktplaats contact uses visible `Bericht` and `Stuur bericht` dialog controls
or an existing message composer. A dedicated labelled worker tab preserves
navigation between CLI calls; the inbox observer has its own background tab. Contact claims and send fingerprints persist
before the external action. There are at most two first-contact attempts per day,
no duplicate listing contacts and no automatic retry of uncertain sends. A click
is reported as unconfirmed until the exact owner message is read in a conversation.

## Verified and remaining

The first real watch ran on the target server, searched live Marktplaats and
selected a 64GB candidate using `qwen2.5-coder:14b` on the M40. Production build,
web session dashboard and systemd timer were checked. Backend full suite: 483
passed; web baseline: 51 passed, typecheck/build clean, lint zero errors and
five existing warnings. Added focused regressions cover delayed first-contact
dialogs, required textbox annotations, server tab continuity, durable replies,
owner cancellation and preservation of public hardware listing paths. The latest
focused shopper/browser/scheduling set passes 33 tests.

A server-only CDP/DOM inbox observer wakes a fixed Python worker when the live
inbox changes. No private marketplace API or message content crosses its browser
binding. Scheduled reply deadlines wake only the due contacts; no five-minute
inbox poll. Restart restores pending deadlines from SQLite. A new seller turn
supersedes pending replies; an owner reply cancels them. Confirmed contacts only
are eligible. Stable 15–45 minute jitter, 08:00–23:00 Europe/Amsterdam and quiet
hours apply. Night-time messages wait until morning; the two-hour target requires
an online server/browser and working site live updates.

Local M40 decisions choose bounded counteroffers, questions about total price,
polite declines or an owner-ready offer. Outbound text is generated from fixed
friendly templates, never arbitrary seller/model instructions. Claims persist
before external clicks; ambiguous sends never repeat. Ready offers appear in the
shopper dashboard and do not accept, reserve or purchase anything.

The server inbox login and actual DOM container were verified. The CDP binding
and DOM trigger were exercised with a local synthetic event. No real incoming
seller reply has yet verified live notification delivery. A real first contact was sent by Leon through the server browser and its exact
owner message was read back in the newly created conversation: delivery confirmed.
Vinted automatic messaging, favourites, TicketSwap event monitoring and
Ticketmaster integration remain open. Checkout/payment is not implemented;
purchases remain the owner's decision.

Private watches, contacts, account tone and browser/test sessions stay outside
Git. Source systemd templates are in `scripts/leon-shopper-watch.*`.
