# Shopper MCP validation

## Marktplaats

Audited source: `jasp-nerd/marktplaats-mcp` release 0.1.1, commit
`8e650274c50c55829ce2917591631665ecd321a6`. PyPI wheel SHA-256:
`429eb3393bad0e7b8200cb946548a00a7f5e6e77454e49683c219bb2b2d3d0a7`.

Validation on Python 3.13 confirmed exact MCP tools:

- `search_listings`
- `get_listing_details`
- `get_seller_profile`
- `list_categories`
- `check_new_listings`

Every tool reported `readOnlyHint=true` and `destructiveHint=false`. One bounded
anonymous search for `fiets`, site `marktplaats`, limit 1, compact output and no
sponsored results completed without MCP error. No returned listing text was kept
in test output. Structured response keys were
`limit,listings,note,offset,returned,site,total_count`; response was 950 bytes with
SHA-256 `07b4fd5a0073e5285c8c1b58760a3fa4ccc0384412cc7996d34d09d97464581f`.

`scripts/leon-install-marktplaats-mcp` installs all dependencies from
`integrations/shopper/marktplaats/requirements.lock` into private runtime storage.
Install fails when Python version, hashes or static package metadata differ. It
does not execute third-party MCP code, enable Gaia binding or accept account
credentials. Exact tool inventory and annotations listed above came from a
disposable audit environment; installer reports `sandbox_attested=false` until
same check passes in rootless Podman with network disabled.

Installer records SHA-256 for every installed runtime file. Later `--verify`
calls reject missing, added or modified files before trusting package metadata.

Lock resolves against public PyPI for Python 3.13. `cryptography==48.0.1` is an
explicit compatibility constraint because newer release metadata was not
available from every tested PyPI edge. Every downloaded artifact remains covered
by `--require-hashes`; source builds are disabled.

Binding stays disabled until rootless Podman attestation passes and runtime can
enforce egress to `www.marktplaats.nl` while blocking every other destination.
Bidding, buying, paying and messaging remain forbidden.
