# Browser en research tool evaluatie

Datum: 2026-08-01  
Taak: `task-browser-en-research-tool-evaluatie`  
Status: kandidaatonderzoek afgerond; geen installatie, geen accountconnectie, geen API-call, geen browser-runtime.

## Productbesluit

Gebruik bestaande projecten waar dat voordeel geeft, maar zet ze niet direct aan. Voor Leon is de efficiënte volgorde:

1. **Firecrawl MCP search-only profiel** als eerste sandbox-kandidaat voor read-only webresearch. Dit past bij bronzoeken, samenvatten en extractie zonder eigen crawler te bouwen.
2. **Playwright MCP** als tweede sandbox-kandidaat voor gecontroleerde browsernavigatie en formulier-previews.
3. **Firecrawl API/full MCP** alleen als search-only onvoldoende is en er een expliciete rate-limit, allowlist en kostenlimiet is.
4. **Browser Use** later evalueren voor complexe browserflows, maar stealth/proxy/captcha-functionaliteit blijft verboden.
5. **Apify MCP** alleen case-by-case wanneer een bewezen Actor veel custom werk voorkomt. Actor execution, agentic payments en paid runs blijven default-deny.

Alles blijft `candidate`. Geen enkele tool is approved, geïnstalleerd of verbonden.

## Scorekaart

| Kandidaat | Repo | Licentie | Live onderhoudssignaal | PM-score | Advies |
| --- | --- | --- | --- | ---: | --- |
| Playwright MCP | `microsoft/playwright-mcp` | Apache-2.0 | actief, push 2026-07-25, 35.719 stars | 79 | Sterke browser-kandidaat, maar high-risk door click/form/download/browser-state. Eerst sandbox met domain allowlist en denied-write tests. |
| Browser Use | `browser-use/browser-use` | MIT | actief, push 2026-07-31, 107.493 stars | 64 | Veel reuse, maar te breed voor vroege enablement. Alleen later sandboxen met stealth/proxy/captcha disabled/forbidden. |
| Firecrawl | `firecrawl/firecrawl` | AGPL-3.0 | actief, push 2026-08-01, 158.984 stars | 75 | Beste read-first extraction fit, maar hosted usage/self-host/crawling/licentie vragen aparte review. |
| Firecrawl MCP Server | `firecrawl/firecrawl-mcp-server` | MIT | actief, push 2026-07-31, 7.099 stars | 77 | Beste eerste MCP-route via search-only profiel; full scrape/interact blijft gated. |
| Apify MCP Server | `apify/apify-mcp-server` | MIT | actief, push 2026-08-01, 2.416 stars | 65 | Handig door Actor marketplace, maar paid actor runs en agentic payments maken dit default high-risk. |

De PM-score komt uit de lokale Leon-toolscore op product fit, reuse, permissieveiligheid, onderhoud, kosten, resource fit, integratiecomplexiteit, vervangbaarheid en adoptiesignaal.

## Vastgelegd in het dashboard

Toegevoegd/geüpdatet in `config/tool-catalog.candidates.json` en de lokale dashboardstore:

- `playwright-mcp-candidate`
- `browser-use-candidate`
- `firecrawl-candidate`
- `firecrawl-mcp-candidate`
- `apify-mcp-candidate`

MCP-intakes aangemaakt:

- `playwright-mcp-candidate`
- `firecrawl-mcp-candidate`
- `apify-mcp-candidate`

Elke intake staat op:

- `execution_allowed=false`
- `install_allowed_now=false`
- `connect_allowed_now=false`
- `write_allowed_now=false`
- `no_approval_granted=true`
- `status_unchanged=true`

## Scope en risico’s

### Playwright MCP

Bron: https://github.com/microsoft/playwright-mcp

Sterk omdat het browser automation via gestructureerde accessibility snapshots biedt. Dat is efficiënter dan vision/screenshot-gestuurde browseragents voor veel flows. Risico zit in echte browseracties: klikken, formulieren invullen, downloads, sessiestatus en mogelijk externe mutaties.

Leon-beleid:

- read-only snapshots mogen pas na sandbox-review;
- submit/click/form-fill alleen met expliciete preview en approval;
- geen login, betaling, posting of formulier-submit zonder gebruiker;
- geen captcha-bypass of anti-bot-evasion.

### Browser Use

Bron: https://github.com/browser-use/browser-use

Sterk door adoption en complexe browser-agentflows. Het project positioneert ook cloud browser infrastructure, proxy rotation en captcha/stealth-gerelateerde capabilities. Dat botst met de Leon-regel dat captcha-bypass, anti-bot-evasion en agressieve scraping verboden zijn.

Leon-beleid:

- niet gebruiken als eerste browserlaag;
- alleen sandboxen als stealth/proxy/captcha-achtige capabilities expliciet disabled of technisch onbereikbaar zijn;
- browser state en persistent filesystem behandelen als gevoelige artefacten;
- hosted/API-gebruik alleen na kostenapproval.

### Firecrawl

Bron: https://github.com/firecrawl/firecrawl

Sterk voor search, scrape, crawl, markdown en structured JSON extraction. Dit voorkomt veel custom crawlerwerk. Risico’s zijn hosted API-kosten, target-site load, ToS/robots-beleid, privacy en AGPL-review bij self-host/embedding.

Leon-beleid:

- start met kleine, bounded read-only research jobs;
- verplicht: rate limit, allowlist, robots/ToS-check, PII-redactie waar mogelijk;
- geen bulk crawl zonder expliciete resource- en kostenapproval;
- AGPL-impact beoordelen vóór code-integratie of self-host wijzigingen.

### Firecrawl MCP Server

Bron: https://github.com/firecrawl/firecrawl-mcp-server

Sterk omdat het Firecrawl als MCP-tool aanbiedt en een smaller search-only profiel heeft. Dat profiel is de beste eerste test, omdat het de tool-surface beperkt en minder snel richting page-fetch/interact/crawl gaat.

Leon-beleid:

- eerst alleen search-only profiel evalueren;
- full scrape/map/deep research apart mappen;
- interact/crawl default-deny;
- `FIRECRAWL_API_KEY` alleen via dashboard secret intake, nooit raw in logs.

### Apify MCP Server

Bronnen:

- https://github.com/apify/apify-mcp-server
- https://docs.apify.com/integrations/mcp

Sterk door duizenden bestaande Actors/scrapers. Dat kan custom bouw fors verminderen. Risico is groter dan bij gewone search: Actor runs kunnen geld kosten, schrijven naar Apify storage, en de Apify MCP-route ondersteunt agentic payment flows.

Leon-beleid:

- actor discovery/docs/read-only mag pas na connect approval;
- actor execution, storage writes en paid runs blijven default-deny;
- agentic payments zijn verboden zonder expliciete, afzonderlijke kostenapproval;
- alleen allowlisted Actors met vaste inputschema’s, kostenplafond en abort-plan.

## Sandbox acceptatiecriteria voor de volgende stap

Voordat één van deze tools runtime krijgt:

1. Maak een sandbox zonder toegang tot raw `.env`-waarden.
2. Gebruik alleen testaccounts/testprofielen.
3. Zet domain allowlist en crawl-rate limits aan.
4. Log alleen redacted metadata, nooit secrets of volledige privécontent.
5. Voeg denied-tests toe voor:
   - raw secret lezen;
   - brede filesystem/network toegang;
   - form submit zonder preview;
   - aankoop/betaling/bid;
   - login zonder gebruiker;
   - captcha-bypass/anti-bot-evasion;
   - agressieve scraping/bulk crawl;
   - prompt-injection die tool permissions probeert te verhogen.
6. Zet rollback klaar: connector uitschakelen, testtoken intrekken, browserprofiel/cache verwijderen, queued crawl/actor jobs aborteren.

## Volgende efficiënte taak

De volgende praktische stap is **`task-local-gpu-model-runtime-readiness`**. Reden: de gebruiker wil dit product op deze machine laten draaien met een waarschijnlijke Tesla M40/P40 of andere NVIDIA GPU. Voor browser/research tools is verdere runtime pas zinvol na sandboxwerk en approvals; GPU/model-runtime readiness raakt de basisarchitectuur en modelkeuze direct.
