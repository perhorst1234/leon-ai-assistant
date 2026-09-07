# Begrensde modeluitvoering

## Werkafspraak — 7 september 2026

Doel: backlogstap 4 en handoffstappen 1–2 uitvoeren: echte tekstgeneratie in de
bestaande WorkQueue, zonder automatische betaalde herhaling. Python/SQLite
blijven de basis. De bestaande dry-run/Agents-SDK-demo blijft inert; deze stap
vervangt niet de algemene agentruntime. Bron: AGENTS.md, handoff.md,
implementation-backlog.md, local-work.md en config/model-routing.json gelezen.

Start: branch codex/night-queue-evidence, HEAD 3faee7f, gelijk aan origin/main.
Gebruikerswerk: gewijzigde .env.example en twee ongetrackte tekstbestanden;
uitsluiten van edits/commits. Sleutelkeuze opgelost door lokale configuratie;
geen live gebruik of budgetinstelling namens de gebruiker.

Latere gebruikerskeuze: sleutelachtige waarde uit .env.example verwijderen.
Alleen die waarde lokaal opgeschoond; overige voorbeeldwijzigingen behouden en
niet gepubliceerd. .env.local is voor/na hash-identiek. De twee losse
tekstbestanden zijn later niet meer aanwezig; niet door deze codewijziging verwijderd.

Code is nodig: de bestaande adapter doet alleen dry-runs en de huidige
read-only retry mag geen betaalde aanvraag herhalen. Architectuurreview: eigen
providertransport en kostenregistratie; WorkQueue blijft eigenaar van taken,
leases en checkpoints. Geen extra verantwoordelijkheid in de grote store.
Maximaal circa 300 regels per nieuwe eigenaar; tests in een aparte module.
Inline uitvoering; TDD mode off, proportionele integratie- en regressietests.

## Contract en uitvoering

1. `openai_text.py`: vaste HTTPS Responses-endpoint, geen redirects/retries,
   begrensde input/output/timeout, bestaande goedkope modelroute, store=false,
   geen tools. Offline tests inspecteren verzoek en parsen echte responsevorm.
2. `model_work.py`: expliciete toestemming voor alleen aangeleverde tekst en
   maximum micro-USD; request-id bindt inhoud/model/limiet. Kosten vóór verzenden
   atomair reserveren. Onzeker verzonden werk nooit automatisch herhalen;
   opgeslagen resultaat na crash hergebruiken. Budgetten gelden per database,
   niet voor andere apps of sleutels. Onzekere reserveringen vervallen niet.
3. Queue/worker/API minimaal koppelen. Bestaande syntaxjobs blijven werken.
   Test toestemming, dubbel verzoek, parallel budgetgebruik, verlopen lease,
   crash rond transport/resultaat, pauze/annulering, foutrespons en secretfilters.
4. Volledige offline backendregressie; werk/risico's hier en in handoff/backlog
   vastleggen en alleen eigen bron publiceren. Geen live API- of hardwareclaim.

Verificatie vanuit repo in een Linux-netwerknamespace met alleen loopback:
`PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider --tb=short`.

## Prijs- en privacygrens

Officiële [modeldocumentatie](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
gelezen op 7 september: bestaande route gpt-5.6-luna, standaard $0,20/M input,
$1,20/M output; cache writes kunnen 1,25× input kosten. De uitvoering rekent
conservatief met $0,25/M input, zonder cachekorting. Tariefcontrole verloopt na
30 dagen; opnieuw verifiëren vóór activering. Dit is geen factuurgarantie.
Reservering gebruikt UTF-8 bytes plus ruime envelopmarge; onverwachte usage boven
die grens bevriest nieuwe calls. Outputlimiet omvat ook reasoningtokens.
[Responses-contract](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).
store=false is geen belofte van zero retention; alleen expliciet gedeelde
tekst gaat naar OpenAI, nooit automatisch de projectmap, database of taakcontext.

## Gebruik en grenzen

- De worker is standaard uit voor OpenAI. Alleen een sleutel instellen activeert
  geen betaalde calls. `LEON_OPENAI_ENABLED=1`, `LEON_OPENAI_DAILY_MICROUSD` en
  `LEON_OPENAI_TOTAL_MICROUSD` moeten bewust in zijn configuratie staan.
  1.000.000 micro-USD = $1. Dagbudget: UTC, totaalbudget: gehele databasehistorie.
  Een nieuwe database is geen voortzetting van hetzelfde kostenplafond.
- De worker leest standaard alleen zijn procesomgeving. Een expliciet lokaal
  bestand kan met `PYTHONPATH=src python3 -m leon_control_plane.local_worker --env-file .env.local`.
  Alleen de vier OpenAI-velden worden gelezen, geen shell uitgevoerd, geen
  globale omgevingsvariabelen gewijzigd; procesinstellingen gaan voor. Dit
  bestand nooit uploaden. Er zijn geen echte budgetwaarden voor Per ingesteld.
- `POST /api/work/model` vereist een dashboard-Bearer-token, óók lokaal en bij
  auth_mode=off. Body bevat uitsluitend `task_id`, UUID `request_id`, `prompt`,
  `max_output_tokens` (1–1024), `max_cost_microusd` en boolean
  `approve_external_text=true`. Dit is toestemming voor die exacte tekst en
  limieten, geen algemene tool- of agentapproval. Parent moet uitvoerbaar en
  low-risk zijn. Maximaal 4096 UTF-8 bytes tekst. De normale jobs-endpoint kan
  geen modelcall maken zonder dit aparte contract.
- Uitvoering blijft één job in WorkQueue. GET jobs/control gebruiken de bestaande
  dashboardbeveiliging; stel `LEON_DASHBOARD_AUTH_MODE=required` in voor alle
  toegankelijke deployments. Het nieuwe model-POST accepteert geen cookie-only
  autorisatie of localhost-bypass. De publieke website is niet opnieuw gedeployd.
- Tijdelijke fouten worden niet automatisch opnieuw betaald. Onzekere uitkomst
  houdt de reservering vast en blokkeert volgende calls totdat gecontroleerde
  reconciliatie is toegevoegd/uitgevoerd. Geen knop om onbewezen kosten vrij te
  geven. Pauze/annuleren kan een al verzonden HTTP-aanvraag niet terughalen.
- Tokens/resultaat worden afzonderlijk vóór het queuecheckpoint opgeslagen.
  Herstart na dat opslagpunt hergebruikt het antwoord zonder nieuwe call.
  De taak kan incompleet/geannuleerd blijven terwijl verbruik wel is vastgelegd.
  Gaia-Werk toont het modeltype, één checkpoint, reservering/verbruik en een
  onzekerheidsmelding. Modelinvoer via Gaia is nog niet aangesloten.

## Verificatie en volgende stap

7 september, laatste bronversie: **231 backendtests en twee subtests geslaagd in
20,64 s**, exit 0 (Ubuntu/WSL, netwerknamespace). **7 webbridge-tests**, TypeScript
en Node-build geslaagd, lint nul errors/vijf al bestaande warnings. Gerichte
controles omvatten echte procescrash na send-marker, HTTP Bearer-vereiste,
gelijktijdige budgetclaims, resultaatcache na verlopen lease, UTC-dagovergang,
tariefverval en expliciete env-file-inlezing met alleen synthetische gegevens.
Vertrouwen B voor deze afgebakende offline integratie, niet voor het volledige
product. `git diff --check` voor eigen bron/docs is schoon.

Offline integratie gebruikt tijdelijke SQLite, synthetische credentials en een
afgesloten netwerknamespace met alleen loopback. Queue, worker, audit, HTTP-API
en Responses-transport met lokale testserver zijn daadwerkelijk uitgevoerd.
De echte OpenAI-server, accounttoegang, facturatie, TLS-handshake en M40 zijn
niet getest. De UI-aanpassing is met TypeScript/build gecontroleerd; nieuwe
modelweergave nog niet opnieuw visueel in de browser geverifieerd.

Volgende code: Gaia-modelinvoer met duidelijke tekst-/kostenapproval, gecontroleerde
reconciliatie en echte chat. Daarna live goedkope smoke-test na expliciete
budgetkeuze. De oorspronkelijke productbacklog blijft volledig van kracht.

Architectuur en overdracht: aligned met backlogstappen 3–5; nieuwe kleine owners
voor providertransport/configuratie en kosten, bestaande queue uitgebreid,
store ongewijzigd en server alleen wiring. De Agents-SDK dry-run blijft behouden
voor zijn expliciete previewcontract; retireer pas als die bredere agentroute
echt geïmplementeerd en de callers gemigreerd zijn. Geen verborgen API-fallback.
