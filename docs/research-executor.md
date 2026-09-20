# Read-only research executor

Leon has a small Firecrawl search-only boundary at `/api/research/status`,
`/api/research/preview` and `/api/research/run`. It is disabled by default and
requires `RESEARCH_EXECUTOR_ENABLED=true`, `FIRECRAWL_API_KEY`, and a non-empty
`RESEARCH_ALLOWED_DOMAINS` allowlist. The key is read only at execution time;
it is never returned, persisted, or included in audit payloads.

Preview normalizes `query`, `allowed_domains` and `max_results` plus server-side
caps and returns an exact SHA-256 `preview_fingerprint` plus durable `preview_id`.
Run requires both within 15 minutes and therefore cannot silently
change the reviewed request. The current limits are 500 query characters, 10
results, 10 domains, 15 seconds and 256 KiB response data. Only Firecrawl's
fixed `https://api.firecrawl.dev/v2/search` endpoint is called, with web search
source metadata; scrape, crawl and structured extraction are not exposed.

Returned sources must use HTTPS and match the allowlist. URLs with credentials,
ports, redirects, or private, reserved, loopback, link-local, multicast or
unspecified addresses are rejected. Permission decisions and execution are
recorded through the connector registry and append-only audit chain. No Night
Queue path invokes this executor automatically.
