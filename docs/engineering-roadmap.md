# Leon AI Assistant — engineering roadmap

Deze roadmap vertaalt het productplan naar bouwbare fases. Afwijkingen van het oorspronkelijke plan zijn alleen bedoeld om sneller tot een betrouwbaar systeem te komen, niet om veiligheids- of kwaliteitslagen over te slaan.

## Gekozen volgorde

1. **Control plane en governance**
   - Voortgangsdashboard, taken, approvals, env intake, audit en auth.
   - Acceptatie: geen secretwaarden in git, state, API responses of logs.

2. **Leon Assistant interface en experience**
   - De echte gebruikersinterface later met de gebruiker specificeren.
   - Acceptatie: interface toont antwoord/proposal/wachten/uitgevoerd duidelijk en omzeilt geen gates.

3. **Core intelligence en governance**
   - Constitution, Task Manager, Decision Layer, Value Engine, approvals, audit en orchestration gates.
   - Acceptatie: route/proposal/task states zijn testbaar, reviewbaar en auditbaar.

4. **Agent runtime en agent teams**
   - Personal, Research, Builder, Debugger, Reviewer, Planner, Manager en Model Scheduler agents.
   - Acceptatie: agents starten via assignment proposals en blijven achter provider/tool gates.

5. **Memory, context en knowledge graph**
   - Memory CRUD, confidence, expiry, source, privacyfilter en graph-relaties.
   - Acceptatie: gebruiker kan zien, corrigeren en verwijderen wat Leon onthoudt.

6. **Tools, MCP en integraties**
   - MCP Hub, toolregistry, GitHub/MCP candidate scoring, browser/research, planner/mail/agenda/school, finance/shopping/tickets/server.
   - Acceptatie: read-only default; externe writes zijn technisch geblokkeerd zonder geldige approval.

7. **Self-learning, research en night improvement**
   - Research Agent, Opportunity/Curiosity/Feedback engines, ochtendrapport, evals en observability.
   - Acceptatie: nachtwerk maakt voorstellen/rapporten, geen stille uitvoering.

8. **Local GPU, deployment en operatie**
   - Modelrouting naar OpenAI/Codex/lokale GPU, Tailscale, healthchecks, backup/restore.
   - Acceptatie: Leon werkt zonder GPU; resource-heavy werk vereist approval.

## Wat nu bewust niet wordt geïnstalleerd

- n8n, Activepieces, Langfuse, Mem0, Graphiti, Cognee, OpenViking zonder aparte fit/security/resource review.
- Vector database of Neo4j.
- MCP-servercatalogus of browser automation.
- Finance, bank, PayPal, tickets, shopper, agenda of mail-integraties.
- OpenHands/OpenCode agents die zelfstandig code uitvoeren.
- GPU stack, vLLM of modeldownloads.
- Night cycle of self-learning engine.

Reden: deze onderdelen zijn nuttig, maar pas veilig nadat control plane, audit, taskmodel, permission manifests en resource/cost gates werken.

## Hergebruik boven custom bouwen

Bestaande GitHub-projecten uit `docs/personal-ai-assistant-plan.md` krijgen de voorkeur als ze aantoonbaar beter zijn dan zelf bouwen. De volgorde is:

1. Registreer repo/MCP-server als candidate manifest in de Tool / MCP registry.
2. Score fit, onderhoud, permissies, security, resource/kosten en vervangbaarheid.
3. Gebruik `approved_readonly` eerst voor onderzoek/metadata.
4. Vraag pas approval voor install, accountkoppeling, write scopes, zware downloads of kosten.
5. Bouw custom alleen wanneer hergebruik te risicovol, te zwaar of te beperkend is.

## Agent-delegatiebeleid

- Subagents krijgen kleine, concrete taken met acceptatiecriteria.
- Subagents krijgen disjuncte write scopes als ze code wijzigen.
- Subagents mogen geen secrets lezen, externe tools installeren, accounts koppelen of productieachtige acties uitvoeren.
- De hoofdreview accepteert of wijst werk af op basis van diff, tests en risico.
