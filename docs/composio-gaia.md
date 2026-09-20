# Composio Gaia contract

`config/composio-bindings.json` records a candidate only. It is version 1,
provider `composio`, role `Planner`, and mode `candidate_disabled`. Loading it
does not install an SDK, create a session, connect OAuth, contact a provider,
or enable a tool.

The contract pins the currently observed toolkit versions: Gmail
`20260903_00` and Google Calendar `20260902_00`. It uses the `direct_tools`
preset and disables meta tools, sandbox, workbench, and remote bash. The
allowlist contains only the exact Gmail fetch actions and Calendar event/free
slot reads in the JSON file. Wildcards and `all` are rejected, and every
write, message, event mutation, connection-management, workbench, bash, and
sandbox capability is explicitly denied.

The loader is intentionally strict about top-level and toolkit keys, toolkit
names and dated versions, exact tool sets, read scopes, denial lists, and
bounded result and timeout limits. Resolution remains denied while the binding
is a candidate; promotion requires a separately reviewed implementation.
