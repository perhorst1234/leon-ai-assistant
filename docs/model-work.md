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
  reconciliatie met ontvangen verbruik is uitgevoerd. Geen knop om onbewezen kosten vrij te
  geven. Pauze/annuleren kan een al verzonden HTTP-aanvraag niet terughalen.
- Tokens/resultaat worden afzonderlijk vóór het queuecheckpoint opgeslagen.
  Herstart na dat opslagpunt hergebruikt het antwoord zonder nieuwe call.
  De taak kan incompleet/geannuleerd blijven terwijl verbruik wel is vastgelegd.
  Gaia-Werk toont het modeltype, één checkpoint, reservering/verbruik en een
  onzekerheidsmelding. Modelinvoer via Gaia is aangesloten zoals hieronder beschreven.

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

## Gaia-invoer — 8 september 2026

Start: `codex/night-queue-evidence`, HEAD `843bc0d`; alleen het aangepaste
`.env.example` was bestaand gebruikerswerk en blijft buiten deze publicatie.
Deze stap maakt de bestaande modelworker vanuit Gaia bruikbaar, zonder nieuwe
provider-, budget- of algemene agentbevoegdheden. Dezelfde queue blijft eigenaar.

- `POST /api/work/model/preview` valideert dezelfde tekst/limieten als verzenden,
  vereist dashboard-Bearer en maakt geen job, reservering of providercall.
- Gaia toont de exacte tekst, het model, de conservatieve reservering en het
  USD-plafond. Approval is standaard leeg en vervalt bij wijziging van taak,
  tekst of plafond. Budgetinstellingen van de worker worden niet veranderd.
- Vóór verzenden bewaart de browser alleen een UUID in sessionStorage. Bij
  onzekere ontvangst gebruikt een bewuste retry dezelfde UUID. De herstelknop
  zoekt via `GET /api/work/jobs?request_id=…`, zonder POST/providercall. Geen
  tekst, dashboardtoken of API-sleutel in browseropslag. Dit is herstel binnen
  hetzelfde tabblad, geen synchronisatie van browsers/apparaten.
- Succes wist de tijdelijke UUID; opgeslagen jobs/antwoorden blijven in SQLite.
  Antwoorden worden als gewone tekst getoond, niet als uitvoerbare model-HTML.

Bewijs: 238 backendtests + twee subtests, 14 webtests, TypeScript/build geslaagd;
lint nul errors/vijf bestaande warnings. Nieuwe regressies dekken mutation-free
preview, Bearer-auth, queryvalidatie, exacte micro-USD, approvalinvalidatie,
opslagfouten, onzeker POST-antwoord en GET-herstel zonder herhaalde verzending.

Desktopbrowser: tijdelijke SQLite, synthetisch dashboardtoken en neptransport
uit `tests/ui_model_fixture.py`; preview toonde lege approval/uitgeschakelde
verzendknop, tekstwijziging verwijderde de goedkeuring, daarna opnieuw goedkeuren
en uitvoeren gaf één afgeronde job (1/1). Na herladen en opnieuw verbinden
bleef dezelfde job `98beb90e` met leesbaar testantwoord aanwezig. Screenshot
visueel gecontroleerd. De fixture roept nooit de echte provider aan.

Vertrouwen B voor deze lokale UI/HTTP/SQLite-keten. Geen mobiele viewporttest,
productiedeployment, echte API-betaling of M40-meting. De onzekere-POST-herstelweg
is automatisch getest, niet door een browsernetwerkfout nagebootst. De
publieke conceptwebsite is niet opnieuw gedeployd. Volgende code: gecontroleerde
kostenreconciliatie en echte chat; volledige productacceptatie blijft open.
De Werk-keuzelijst toont maximaal de 100 nieuwste jobs. UUID-herstel kan een
oudere job vinden, maar die verschijnt nog niet automatisch buiten die lijst;
detailnavigatie voor oudere jobs is een open UI-beperking.

## Werkafspraak: herstel van waargenomen kosten

Start HEAD `33d4c1a`, alleen `.env.example` gebruikersdelta. Risico: middel/hoog
omdat kosten vrijvallen; bestaande provider-/prijs-/approvalgrenzen blijven intact.
Nodige code: verbruik vóór antwoordparsing duurzaam opslaan, daarna kosten-only
reconciliatie met exact goedgekeurde receipthash. Geen imports van zelfverklaarde
kosten en geen aannames bij timeout zonder verbruik. Architectuur: aparte kleine
receipt-owner naast model_work; dezelfde SQLite-transactie en queue, server wiring.
Test met neptransport: misvormd antwoord, ontbrekend/bovenmatig verbruik, crash,
dubbele/concurrerende approval, rollback, late worker en HTTP-autorisatie.

Uitgevoerd: `model_receipts.py` bewaart alleen gevalideerde model/status/token-
aantallen, kostenberekening en job-/request-/approvalbinding, vóór de parsing
van het antwoord. Geen ruwe response, tekst of API-key in de receipt. De
bestaande SQLite-database is vertrouwd: de hash bindt de getoonde approval en
detecteert inconsistentie, maar is geen bewijs tegen iemand met schrijfrecht
op de database en geen geverifieerde factuur.

`GET /api/work/model/reconciliation?id=…` geeft een kostenvoorstel, alleen voor
unknown/reconciled met geldige receipt. `POST` accepteert uitsluitend `id`,
`receipt_sha256` en `approve_cost_reconciliation=true`, met dashboard-Bearer
ook op localhost/auth-off. Kosten zijn server-side berekend, nooit ingevoerd
door de browser. Gaia gebruikt dezelfde lokaal begrensde proxy en toont het
voorstel met een lege approval. Pas na bevestigen wordt de resterende hold
vrijgegeven; andere reeds goedgekeurde jobs kunnen dan binnen hun budget verder.

Kostenafboeking/audit zijn één transactie en idempotent. De oorspronkelijke job
en foutcheckpoints blijven intact; er wordt geen antwoord of succes verzonnen.
Een late worker respecteert de reconciled-status. Ontbrekende usage, onbekend
model, niet-finale status, bovenmatige tokens of ontbrekende receipt blijven
geblokkeerd. Oude jobs zonder deze receipt zijn niet achteraf bewijsbaar via
dit pad. Geen automatische providerraadpleging of receipt-import.

Verificatie: **253 backendtests + twee subtests in 23,54 s**, exit 0, Ubuntu/WSL
in netwerknamespace met alleen loopback. **16 webtests**, TypeScript/build
geslaagd; lint nul errors/vijf bestaande warnings. Gerichte nieuwe tests:
readonly preview, onbruikbaar antwoord met geldige usage, ongeldige/ontbrekende
usage, dubbele/concurrerende approval, auditrollback, receiptintegriteit,
gereconstrueerde worker na opslag en een late worker tijdens reconciliatie.

Desktopbrowser met `tests/ui_model_fixture.py --broken-answer`: tijdelijke SQLite,
synthetische credentials/provider; job `9cac27a6` bleef na preview onveranderd.
Goedkeuren veranderde de reservering van $0.000416 naar nul en boekte $0.000021
synthetisch verbruik af. Job bleef onafgerond 0/1, herstelmelding zichtbaar en
visueel gecontroleerd. Geen echte betaalde call of M40-/mobiele productieproef.
Vertrouwen B voor dit afgebakende herstelpad; niet voor de volledige productvisie.

Complexiteit binnen scope: receipt-owner 88 regels, aparte kleine UI/lib/tests,
gedeelde usageparser en bestaande queue/DB; grote server alleen routing.
Deze stap behoudt de no-retrygrens en maakt geen tweede runtime. Volgende code:
echte chat en oudere-jobdetailherstel, daarna read-only connector. Bewijsloze
netwerkuitkomsten blijven een bewuste blokkade, niet stilzwijgend kwijtgescholden.

Complexiteit: kleine aparte formulier-/verzendowners, bestaande proxy/API/queue
uitgebreid, grote server alleen wiring en store ongewijzigd. Demo blijft expliciet
gescheiden tot de volledige chat/agentroute is geïmplementeerd; geen tweede
runtime of fallback toegevoegd. Code en bewijs volgen backlogstappen 3–5.
