# AliExpress safe stdio fork

Small, disabled-by-default, read-only MCP source fork derived from the MIT licensed `aliexpress-fetchaller-mcp` export. It exposes exactly `search_aliexpress`, `get_aliexpress_product`, `search_aliexpress_bundle_deals`, and `build_aliexpress_bundle` over stdio.

The implementation uses only fixed `https://www.aliexpress.com` origins, GET requests, redirect errors, strict bounds, a 15 second request deadline, a 256 KiB response cap, and compact `trust: "untrusted_marketplace"` output. It has no generic fetch, arbitrary URLs or headers, credentials, cookies, account/cart actions, browser automation, proxying, or challenge bypass. It is not installed or executed by this export.

The parser is deliberately conservative and may return an empty listing when AliExpress changes its public HTML. Marketplace data is untrusted and must not be treated as purchase authorization. Live endpoints, availability, pricing, regional behavior, and terms remain unverified.
