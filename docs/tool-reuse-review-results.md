# Tool reuse review results

Datum: 2026-08-01

Scope: read-only fit/security/license review voor de drie `evaluate_now` kandidaten uit de Leon tool registry. Deze review is geen install, geen account-connectie, geen approval, geen manifest-promotie en geen runtime-enablement.

## Samenvatting

| Kandidaat | Reviewbeslissing | Wat betekent dit concreet |
| --- | --- | --- |
| LiteLLM | `sandbox_before_decision` | Product-fit voor modelgateway/failover/budget-routing, maar eerst geïsoleerde sandbox door brede secret-surface en supply-chain risico. |
| OpenAI Agents SDK | `sandbox_before_decision` | Sterke eerste real-runtime kandidaat, maar eerst beperkte sandbox zonder shell/MCP/hosted tools/computer/apply-patch surfaces. |
| Model Context Protocol servers | `reuse_readonly_after_review` | Bruikbaar als catalogus/oriëntatiebron. Geen enkele individuele MCP server is hiermee goedgekeurd. |

## LiteLLM

Beslissing: `sandbox_before_decision`.

Product-fit is aanwezig voor provider-abstraction, failover, load balancing, budget/rate-limit routing en OpenAI-compatible proxying. Leon heeft echter al een eigen simpele modelrouting en OpenAI Agents SDK is de primaire eerste runtime-kandidaat. LiteLLM moet daarom later als gateway-laag worden getest, niet nu als core dependency.

Bewijsbronnen:

- Lokale kandidaat: `config/tool-catalog.candidates.json`
- Lokale modelrouting: `config/model-routing.json`
- Lokale gate-regels: `docs/mcp-tool-permission-model.md`
- Officiële repo: https://github.com/BerriAI/litellm
- Officiële docs: https://docs.litellm.ai/
- Routing/load-balancing docs: https://docs.litellm.ai/docs/routing-load-balancing
- Key/config docs: https://docs.litellm.ai/docs/set_keys
- Production best practices: https://docs.litellm.ai/docs/proxy/prod
- License: https://raw.githubusercontent.com/BerriAI/litellm/main/LICENSE
- Security policy: https://raw.githubusercontent.com/BerriAI/litellm/main/security.md
- Security incident: https://docs.litellm.ai/blog/security-update-march-2026

Belangrijkste gates:

- Geen unpinned install. Bekende gecompromitteerde PyPI-versies `1.82.7` en `1.82.8` expliciet blokkeren.
- Sandbox alleen in disposable venv/container, niet in de Leon repo zelf.
- Geen toegang tot `/home/per`, `.env.local`, SSH keys, cloud credentials of echte Leon secrets.
- Proxy alleen lokaal binden op `127.0.0.1`; geen Tailscale/public exposure in eerste sandbox.
- Alleen keynamen registreren, geen waarden tonen of in agentcontext stoppen.
- Leon blijft bron van waarheid voor approvals, audit, modelroute-redenen en secret-presence metadata.
- Niet bouwen op enterprise-only features zonder expliciete licentie-/kostenkeuze.

Latere sandbox-acceptatiecriteria:

- Versie pinned met hash/signature of release-verificatie.
- Alleen één simpele route: Leon route -> LiteLLM alias -> één testmodel.
- Fallback-test met laag-risico prompt.
- Logs gecontroleerd op prompt/secret leakage.
- Rollback getest: sandbox verwijderen, testkeys intrekken, config weggooien, geen persistente DB tenzij expliciet goedgekeurd.

## OpenAI Agents SDK

Beslissing: `sandbox_before_decision`.

Product-fit is sterk voor een Python-first agent runtime: agent loop, tool-calling, handoffs, sessions, guardrails, human review en tracing passen bij Leon. De SDK mag nog niet direct actief worden, omdat beschikbare tool-surfaces zoals MCP, shell, computer, hosted tools en apply-patch side effects kunnen veroorzaken als Leon’s eigen permission preflight niet vóór elke toolcall blijft zitten.

Bewijsbronnen:

- Lokale runtimekeuze: `docs/agent-runtime-provider-decision.md`
- Lokale providerconfig: `config/agent-runtime-provider.json`
- Lokale kandidaat: `config/tool-catalog.candidates.json`
- Officiële repo: https://github.com/openai/openai-agents-python
- Officiële docs: https://openai.github.io/openai-agents-python/
- OpenAI Agents guide: https://developers.openai.com/api/docs/guides/agents
- Guardrails docs: https://openai.github.io/openai-agents-python/guardrails/
- License: https://raw.githubusercontent.com/openai/openai-agents-python/main/LICENSE
- Security policy: https://raw.githubusercontent.com/openai/openai-agents-python/main/SECURITY.md

Belangrijkste gates:

- `local_mock` blijft default totdat een aparte sandbox/adapter gate slaagt.
- Alleen `OPENAI_API_KEY` als required env-key naam; geen waarde in logs/API/audit.
- Geen ShellTool, ApplyPatchTool, ComputerTool, hosted MCP, web/file/code tools in eerste sandbox.
- Leon permission preflight vóór elke custom function-tool uitvoering.
- Tracing/redaction expliciet testen of tracing per run uitzetten.
- Geen install/activation zonder expliciete approval.

Latere sandbox-acceptatiecriteria:

- Disabled-by-default adapter achter `local_mock` fallback.
- Eén read-only text-agent run zonder tools, met modelrouting en audit events.
- Daarna één function-tool demo met Leon permission preflight vóór uitvoering.
- Geen raw `.env.local` reads; alleen scoped client-injectie.
- Rollback getest: providerconfig terug naar `local_mock`, dependency/venv/container verwijderen, geen statuspromotie.

## Model Context Protocol servers

Beslissing: `reuse_readonly_after_review`.

Deze kandidaat is nuttig als catalogus en oriëntatiebron voor tool reuse. Dit is geen trustlist. Iedere concrete MCP server blijft een eigen candidate met eigen manifest, source pinning, licentiecheck, scope-map, sandbox en approval gates.

Bewijsbronnen:

- Lokale kandidaat: `config/tool-catalog.candidates.json`
- Lokale permissionregels: `docs/mcp-tool-permission-model.md`
- Lokale productcontracten: `docs/product-constitution-and-component-contracts.md`
- MCP servers repo: https://github.com/modelcontextprotocol/servers
- MCP registry repo: https://github.com/modelcontextprotocol/registry
- MCP spec: https://modelcontextprotocol.io/specification/2025-06-18
- MCP security best practices: https://modelcontextprotocol.io/docs/draft/tutorials/security/security_best_practices
- MCP servers license: https://raw.githubusercontent.com/modelcontextprotocol/servers/main/LICENSE
- MCP servers security policy: https://raw.githubusercontent.com/modelcontextprotocol/servers/main/SECURITY.md

Belangrijkste gates:

- Catalogus is geen trusted allowlist.
- Reference implementations zijn geen production-ready garantie.
- Licentie is op projectniveau in transitie; per server/package/release vaststellen.
- MCP tool descriptions, schemas en prompts als untrusted input behandelen.
- Filesystem, git, browser, OAuth, API writes, local process en netwerktoegang apart modelleren.
- Install/connect/write/resource-heavy acties blijven approval-gated.

Latere individuele MCP-server acceptatiecriteria:

- Exacte bron vastgelegd: repo/package/release/commit, maintainer, license, security policy en freshness.
- Toolschema volledig gemapt naar Leon manifest: read scopes, write scopes, env keys, network/file/process access en externe effecten.
- Default deny; alleen expliciet toegestane read-only acties zonder approval.
- Sandbox met lege testworkspace, geen echte secrets, geen user-home access en audit logging.
- Write tools pas na preview, consumed approval id en rollbackplan.
- Security review voor dependency/vulnerability, prompt/tool poisoning en OAuth/redirect/client consent indien relevant.

## Dashboard en state-uitkomst

De drie lokale review-taken mogen op `done` met deze beslissingen:

- `Review reuse candidate: LiteLLM`: done als review, kandidaat blijft gated met `sandbox_before_decision`.
- `Review reuse candidate: OpenAI Agents SDK`: done als review, kandidaat blijft gated met `sandbox_before_decision`.
- `Review reuse candidate: Model Context Protocol servers`: done als catalogusreview, individuele MCP servers blijven apart gated.

Niet uitgevoerd:

- geen package install;
- geen repo clone;
- geen account connect;
- geen API key gelezen;
- geen `.env.local` gelezen;
- geen approval aangemaakt of geconsumeerd;
- geen manifest status gepromoveerd;
- geen externe write of runtime enablement.
