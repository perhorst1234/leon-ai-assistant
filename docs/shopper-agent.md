# Shopper agent

Leon now has bounded shopper planning primitives in
`src/leon_control_plane/shopper_agent.py`. They accept normalized listings,
filter hard constraints, rank the remaining deals, learn only coarse style
signals from user supplied message examples, and produce a weekly watch plus a
reviewable offer proposal.

The shopper is read-only by default. A proposal contains the exact listing,
offer amount and message, and always carries `approval_required=true` before an
external message or bid can be sent. Likes, account changes, purchases and
payments use the same gate. No password, cookie, CAPTCHA bypass, proxy rotation
or private endpoint is accepted.

The current Marktplaats and Vinted MCP entries are disabled candidates until
their source, network boundary and account scopes are attested. The official
Marktplaats API documentation is the route for a real OAuth connector. Vinted's
official documentation covers allowlisted Pro integrations; consumer messaging,
bidding and likes are not enabled by the current adapter. The supplied third
party repositories can be audited as read-only research inputs, but they do not
change those gates.

To personalize the writing style, provide a small set of your own sent
messages or an approved export. The agent stores a compact style profile, not a
copy of your account history.

## TicketSwap

`src/leon_control_plane/ticketswap_agent.py` adds the same read-only pattern for
personal event tickets: event search, price and seller comparison, and a weekly
watch. It excludes resale workflows. TicketSwap has no verified public
developer API in the current connector review, so this remains a candidate
until an official account flow is available. Opening a checkout or purchasing a
ticket is always a separate approval action.
