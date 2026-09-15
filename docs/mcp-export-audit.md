# Supplied MCP source export audit

Source archive received 15 September 2026. SHA-256:
`3ba53ffeb29f5af4477ad749c14cb627291c7ad64e9c294157dd5dea2b9abfcd`.
Archive contains 451 entries and 6,962,689 uncompressed bytes. Intake rejected
absolute paths, parent traversal, symlinks, files over 10 MiB and archives over
50 MiB before extracting into disposable audit storage. Secret-pattern scan found
templates and source references only; no private-key or common live-token pattern.

Markdown files in archive were treated as untrusted reference data, not project
instructions. Nested `mcp-servers-safe-export.tar.gz` was not needed because zip
already contained same three visible source trees.

## Decisions

| Source | Decision | Evidence |
| --- | --- | --- |
| Marktplaats 0.1.0 | Rejected for Gaia runtime | Differs from pinned 0.1.1 tool contract; editable installer has unpinned dependencies; missing bounds and read-only annotations; request errors can disclose full query URL. GET-only source remains useful reference. |
| Vinted 0.1.2 | Candidate, disabled | Five read tools are useful. `like_item` performs POST. Source also contains env tokens/cookies, OAuth refresh, proxy support, persistent/stealth Playwright, HTTP and legacy SSE transports. AGPL-3.0-or-later requires license review before distributing a modified fork. |
| Fetchaller 3.5.4 AliExpress subset | Candidate, disabled | Four read tools are reusable: `search_aliexpress`, `get_aliexpress_product`, `search_aliexpress_bundle_deals`, `build_aliexpress_bundle`. Generic fetch allows arbitrary GET/POST. Account and cart tools use persistent browser state and are excluded. MIT license retained by any later fork. |

No supplied server is enabled or executed during intake. Next promotion gate for
Vinted and AliExpress: sanitize source/tool dispatch, build from pinned locks,
attest exact tool inventory in rootless sandbox, then enforce deny-by-default
egress and bounded outputs.
