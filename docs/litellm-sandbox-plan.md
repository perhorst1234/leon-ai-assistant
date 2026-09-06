# LiteLLM isolated gateway sandbox plan

Status: plan-only  
Datum: 2026-08-01  
Beslissing uit reuse review: `sandbox_before_decision`

Dit document beschrijft een geïsoleerde LiteLLM sandbox voor Leon. Dit is geen installatie-opdracht, geen proxy-start, geen accountconnectie, geen approval en geen modelrouting-promotie. Uitvoering vereist later expliciete approval voor install/API-gebruik.

## Doel

Vaststellen of LiteLLM nuttig is als beperkte gateway-laag voor:

- provider abstraction;
- fallback/load-balancing;
- budget/rate-limit routing;
- OpenAI-compatible proxying.

Leon blijft altijd bron van waarheid voor:

- routebeslissing en modelreden;
- approvals;
- audit;
- task status;
- secret presence metadata;
- permission checks.

## Bronnen

- Lokale kandidaat: `config/tool-catalog.candidates.json`
- Lokale modelrouting: `config/model-routing.json`
- Lokale reuse review: `docs/tool-reuse-review-results.md`
- LiteLLM repo: https://github.com/BerriAI/litellm
- LiteLLM docs: https://docs.litellm.ai/
- Routing/load-balancing: https://docs.litellm.ai/docs/routing-load-balancing
- Proxy config: https://docs.litellm.ai/docs/proxy/configs
- Production best practices: https://docs.litellm.ai/docs/proxy/prod
- Master key/virtual keys: https://docs.litellm.ai/docs/proxy/virtual_keys
- License: https://raw.githubusercontent.com/BerriAI/litellm/main/LICENSE
- Security policy: https://raw.githubusercontent.com/BerriAI/litellm/main/security.md
- Official security update: https://docs.litellm.ai/blog/security-update-march-2026

## Hard gates

Geen sandbox-uitvoering als één van deze punten ontbreekt:

- expliciete approval voor install/API-gebruik;
- disposable venv/container buiten de Leon runtime;
- pinned LiteLLM versie;
- denylist voor bekende gecompromitteerde versies `1.82.7` en `1.82.8`;
- artifact/hash of release-provenance check;
- localhost-only binding;
- geen real user-home mount;
- geen `.env.local` read;
- geen echte brede providerkey set;
- log-redaction testplan;
- rollbackplan.

## Sandbox scope

Toegestaan na approval:

- disposable omgeving aanmaken;
- pinned package/container artifact evalueren;
- proxy alleen op `127.0.0.1`;
- één testprovider of dummy providerroute;
- één laag-risico prompt via Leon route -> LiteLLM alias -> testmodel;
- fallback-test met gesimuleerde providerfail;
- logscan op secret/prompt leakage;
- rollback.

Niet toegestaan:

- proxy op Tailscale/public host;
- admin UI extern openzetten;
- echte persoonlijke prompts;
- echte multi-provider keyset;
- MCP/agent gateway features;
- management API write-paths buiten test;
- persistent database met echte credentials;
- gebruik van enterprise-only features zonder licentie/prijsbesluit.

## Env-key namen voor latere sandbox

Minimum:

- `OPENAI_API_KEY`
- `LITELLM_MASTER_KEY`

`LITELLM_MASTER_KEY` is voor de sandbox een nieuwe test/admin key, geen bestaande productiekey. De waarde blijft buiten docs, dashboard, audit en agentcontext.

Optioneel, alleen als expliciet gekozen:

- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `XAI_API_KEY`
- `AZURE_API_KEY`
- `AZURE_API_BASE`
- `AZURE_API_VERSION`
- `FIREWORKS_AI_API_KEY`
- `DATABASE_URL`
- `LITELLM_SALT_KEY`
- `REDIS_URL`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST`

Regels:

- Alleen keynamen en presence worden getoond.
- Geen secretwaarden in config templates, dashboard, audit, logs of task output.
- Master/admin key wordt behandeld als high-sensitivity secret.

## Supply-chain check

Voor latere uitvoering:

- controleer gekozen versie tegen denylist;
- controleer release notes/security advisories;
- controleer artifact/hash of container digest;
- bewaar bewijs in taakresultaat;
- log geen package manager cachepaden met user secrets;
- verwijder sandbox/cache na test.

## Acceptance tests voor latere uitvoering

De LiteLLM sandbox slaagt alleen als:

- proxy alleen luistert op `127.0.0.1`;
- management/admin routes niet zonder master key bereikbaar zijn;
- Leon kiest het model en LiteLLM voert alleen de provider-call abstraction uit;
- fallback werkt zonder Leon’s audit/modelroute te verliezen;
- logs bevatten geen secretwaarden of raw testkey;
- prompt met fake secret wordt geredact;
- providerkosten blijven binnen vooraf goedgekeurde limiet;
- audit hash-chain blijft valide;
- rollback verwijdert sandboxomgeving, testconfig en eventuele testkeys.

## Approval die later nodig is

Een latere sandbox-uitvoering vereist een approval-card met:

- actie: disposable LiteLLM sandbox installeren/starten;
- scope: localhost-only, één testmodel/alias;
- kosten: vaste max voor testcalls;
- risico: supply-chain + secret concentration;
- rollback: omgeving verwijderen, testkeys intrekken, config weggooien;
- expiry: éénmalige korte geldigheid.

## Dashboard taak-uitkomst

De taak `Maak sandboxplan voor LiteLLM isolated gateway test` mag op `done` wanneer dit document is vastgelegd en geverifieerd. Het plan zelf voert niets uit.
