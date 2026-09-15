# Vinted safe stdio fork

This is a statically reviewed, read-only fork derived from the archived source at `servers/vinted-mcp` (archive SHA-256: `3ba53ffeb29f5af4477ad749c14cb627291c7ad64e9c294157dd5dea2b9abfcd` as supplied for this export). It exposes only `search_items`, `get_item`, `get_seller`, `compare_prices`, and `get_trending`, in Dutch, over stdio.

Status: disabled by default; sandbox-required. The implementation is intentionally limited to exact `https://www.vinted.nl` requests, with bounded inputs and outputs. No credentials, browser session, proxy, or write operation is supported. No third-party code is executed by the audit.

The included `audit.mjs` performs static forbidden-string and policy checks. Dependencies are not installed as part of this fork.
