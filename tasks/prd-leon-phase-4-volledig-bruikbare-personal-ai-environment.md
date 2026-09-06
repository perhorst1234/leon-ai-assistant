# Leon Phase 4: Volledig Bruikbare Personal AI Environment

## Doel

Phase 4 maakt Leon praktisch af: na deze fase moet Leon dagelijks bruikbaar zijn als lokale personal AI environment, met alleen nog finetuning op basis van gebruikersfeedback. Leon moet kunnen chatten, taken kiezen, werk uitvoeren, approvals vragen, browser/web research doen, modelrouting toepassen, GPU-capaciteit gebruiken waar dat kosten bespaart, en een productwaardig dashboard bieden voor controle, status en bewijsvoering.

## Context

Eerdere fases hebben de basis gelegd voor PRD/task-state, control-plane, modelrouting, autonome werkvoorstellen, risk levels, Night Queue, Morning Brief en dashboard-specificaties. Phase 4 bundelt dit tot één werkend systeem.

Belangrijke nieuwe scope:
- Dit is **Phase 4**, niet Phase 3.
- De NVIDIA Tesla M40 24GB moet volledig worden aangesloten voor lokale inference/acceleratie.
- API-kosten moeten omlaag door lokaal te draaien waar dat stabiel en nuttig is.
- De chassis fan die fysiek op/voor de GPU zit moet via een script/service aan GPU-temperatuur gekoppeld worden.
- Browser/web research hoort in de eerste echte workflow.
- UI/dashboard moet voelen als finale app, met alleen feedback-finetuning daarna.

## Productdoel

Leon is na Phase 4 een geïntegreerde dagelijkse werkmachine:

1. De gebruiker kan met Leon chatten.
2. Leon kan zelf waardevol werk kiezen uit taken, plannen en repo-context.
3. Leon kan veilig uitvoeren binnen ingestelde grenzen.
4. Leon vraagt approval voor risicovolle acties.
5. Leon gebruikt lokale GPU-modellen waar dat goedkoper/stabiel genoeg is.
6. Leon kan browser/web research doen.
7. Leon kan avond/nacht werk plannen.
8. Leon levert een Morning Brief met bewijs, wijzigingen, blokkades en voorgestelde vervolgstappen.
9. De gebruiker kan alles volgen en bijsturen via dashboard/CLI/TUI.

## Succescriteria

Phase 4 is geslaagd als:

- Leon voert minimaal één realistische taak end-to-end uit vanuit chat.
- Leon kiest zelf werk, voert veilig uit en vraagt approval waar nodig.
- Night Queue draait een echte workflow en Morning Brief toont resultaat met bewijs.
- GPU-route is gevalideerd op de M40 24GB.
- Modelrouting gebruikt lokaal waar dat goedkoper is en API waar dat beter/noodzakelijk is.
- Fan-control service draait en koppelt chassis fan aan GPU-temperatuur.
- Dashboard is productwaardig: status, controls, approvals, audit, queue, brief, foutstates en responsive layout werken.
- Alleen finetuning, feedback, prompts, thresholds en kleine UI-aanpassingen blijven over.

## Scope

### In Scope

- Chat-to-action workflow
- Task/prioritization engine
- Autonomous work loop
- Approval/risk gate system
- Browser/web research worker
- Night Queue
- Morning Brief
- Memory/context layer
- Modelrouting
- Local GPU runtime voor M40 24GB
- `llama.cpp` én Ollama validatie, daarna beste/stabielste route kiezen
- Kostenbewuste routing: lokaal eerst waar mogelijk, API alleen wanneer nodig
- Chassis fan GPU-temp service
- Productwaardig dashboard
- Audit log en bewijsvoering
- Tailscale/remote toegang als onderdeel van dagelijkse workflow
- CLI/TUI control waar nuttig

### Out of Scope

- Mail/calendar write-integraties in Phase 4
- Volledig onbeperkte externe acties zonder approval
- Nieuwe hardware-aankoop behalve als blocker expliciet wordt vastgesteld
- Perfecte modelkwaliteit
- Volledige enterprise multi-user security
- Niet-lokale cloud GPU infrastructuur tenzij later apart besloten

## Autonomiebeleid

Leon mag breed autonoom werken, maar met harde approval-grenzen.

Altijd approval-first:

- Destructief systeemwerk, zoals delete/reset/driver/service changes
- Externe writes, zoals mail sturen, accounts koppelen of public deploys
- Public-facing wijzigingen
- Credential/token/security wijzigingen
- Grote downloads of acties met duidelijke kostenimpact
- Acties die data buiten de lokale omgeving sturen
- Risk level R4+ acties

Leon mag zelfstandig:

- Lokale repo’s lezen
- Taken/plannen analyseren
- Voorstellen maken
- Lokale niet-destructieve wijzigingen voorbereiden
- R1-R3 werk uitvoeren als policy dit toestaat
- Browser/web research doen
- Samenvattingen, diffs, briefs en next actions maken
- Lokale modellen gebruiken binnen resource limits

## Modelrouting en Kostenbeleid

Doel: zo min mogelijk API-kosten zonder bruikbaarheid te verliezen.

Leon moet modelkeuze bepalen op basis van:

- Taaktype
- Benodigde kwaliteit
- Privacygevoeligheid
- Kosten
- Latency
- GPU-beschikbaarheid
- Contextlengte
- Fallback-betrouwbaarheid

Routingregels:

- Gebruik lokale M40-route voor standaard reasoning, samenvatten, classificatie, embeddings/batch waar stabiel.
- Gebruik API alleen voor taken die lokaal onvoldoende kwaliteit halen, te traag zijn of speciale capaciteiten nodig hebben.
- Toon in dashboard welke route gebruikt is en waarom.
- Log geschatte kostenbesparing per taak of sessie.
- Val automatisch terug naar API of CPU-route als GPU-route faalt, maar markeer dat zichtbaar.

## GPU Runtime Requirements

De M40 24GB moet als echte runtime-capaciteit worden aangesloten.

Vereisten:

- Detectie van GPU, driver, CUDA/NVIDIA stack en VRAM.
- Validatie van temperatuur, geheugen, power state en stabiliteit.
- Installatie/validatiepad voor zowel Ollama als `llama.cpp`.
- Benchmark van minimaal één bruikbaar lokaal model.
- Selectie van standaard backend op basis van stabiliteit, kostenbesparing en performance.
- Modelrouting-config koppelt gevalideerde lokale backend aan Leon.
- Dashboard toont GPU-status, backend, model, VRAM, temperatuur en laatste fout.
- GPU-heavy jobs krijgen limieten zodat het systeem bruikbaar blijft.
- Fallback wanneer GPU-runtime niet beschikbaar is.

## Fan-Control Requirements

Buiten Leon Assistant moet een script/service de chassis fan aan GPU-temperatuur koppelen.

Vereisten:

- Service leest GPU-temperatuur periodiek uit.
- Fan curve vertaalt temperatuur naar fan speed.
- Service start automatisch of is eenvoudig via CLI te starten.
- Failsafe bij sensorfout of hoge temperatuur.
- Logging van temperatuur, fan state en errors.
- Dashboard mag status tonen, maar fan-control moet niet afhankelijk zijn van het dashboard.
- Geen destructieve hardware/service wijzigingen zonder expliciete approval tijdens uitvoering.

Minimale fan curve:

- Laag bij veilige idle temperatuur
- Midden bij normale load
- Hoog bij zware load
- Max/failsafe bij kritieke temperatuur

Exacte thresholds mogen tijdens implementatie worden bepaald op basis van hardwaremeting.

## Dagelijkse Workflow

Phase 4 levert één geïntegreerde workflow:

1. Leon scant taken, PRD’s, docs, repo-status en actuele context.
2. Leon kiest waardevol werk op basis van prioriteit, risico en haalbaarheid.
3. Leon maakt een plan.
4. Leon voert laag-risico werk zelfstandig uit.
5. Leon vraagt approval voor riskante acties.
6. Leon gebruikt browser/web research waar nodig.
7. Leon gebruikt lokale GPU/API volgens modelrouting.
8. Leon logt bewijs, wijzigingen, fouten en keuzes.
9. Leon draait Night Queue voor gepland werk.
10. Leon levert Morning Brief met resultaten, blockers en next actions.

## Dashboard Requirements

Dashboard moet productwaardig zijn.

Belangrijke schermen/gebieden:

- System status
- Chat/workflow status
- Task queue
- Night Queue
- Morning Brief
- Approvals
- Audit log
- Modelrouting
- GPU status
- Fan service status
- Browser research status
- Errors/fallbacks
- Settings/controls

Kwaliteitseisen:

- Responsive layout
- Goede lege states
- Goede foutstates
- Duidelijke filters
- Heldere approval controls
- Geen ruwe debug-UI als primaire interface
- Statussen moeten begrijpelijk zijn zonder terminal
- Finale-app gevoel, alleen feedback-finetuning blijft over

## User Stories

### US-001 Chat-to-Work

Als gebruiker wil ik met Leon kunnen chatten en vanuit chat echt werk kunnen starten, zodat Leon niet alleen antwoord geeft maar ook helpt uitvoeren.

Acceptance criteria:
- Chat kan taakcontext ophalen.
- Leon kan plan en voorgestelde acties tonen.
- Leon kan veilige acties starten.
- Approval wordt gevraagd waar nodig.
- Resultaat komt terug in chat en audit log.

### US-002 Autonomous Prioritization

Als gebruiker wil ik dat Leon zelf ziet welk werk waardevol is, zodat ik niet alles handmatig hoef te sturen.

Acceptance criteria:
- Leon leest taken/plannen/docs.
- Leon rangschikt werk op waarde, urgentie, risico en afhankelijkheden.
- Leon kiest een eerstvolgende actie.
- Keuze wordt uitgelegd in dashboard/Morning Brief.

### US-003 Safe Autonomous Execution

Als gebruiker wil ik dat Leon zelfstandig werkt maar niet roekeloos handelt.

Acceptance criteria:
- Risk levels worden toegepast.
- R1-R3 kan zelfstandig waar policy dit toestaat.
- R4+ vraagt approval.
- Destructieve systeemacties en externe writes vragen altijd approval.
- Audit log toont acties en beslissingen.

### US-004 GPU-Backed Local Intelligence

Als gebruiker wil ik dat Leon de M40 gebruikt om API-kosten te besparen.

Acceptance criteria:
- GPU wordt gedetecteerd.
- Ollama en `llama.cpp` zijn gevalideerd of duidelijk afgewezen.
- Beste backend is gekozen.
- Minimaal één lokaal model werkt.
- Routing gebruikt lokaal waar mogelijk.
- Dashboard toont GPU/modelstatus.

### US-005 Cost-Aware Routing

Als gebruiker wil ik dat Leon niet onnodig API-kosten maakt.

Acceptance criteria:
- Routing kiest lokaal voor geschikte taken.
- API-gebruik wordt verklaard.
- Fallbacks zijn zichtbaar.
- Dashboard toont routekeuze en kostenindicatie.

### US-006 Browser/Web Research

Als gebruiker wil ik dat Leon web research kan doen wanneer actuele informatie nodig is.

Acceptance criteria:
- Leon kan browser/web research starten.
- Resultaten worden samengevat met bronnen.
- Research wordt gekoppeld aan taakcontext.
- Externe write-acties blijven approval-first.

### US-007 Night Queue

Als gebruiker wil ik dat Leon werk kan klaarzetten en ’s avonds/nachts uitvoeren.

Acceptance criteria:
- Queue kan taken plannen.
- Queue respecteert risk gates.
- GPU/API limits worden gerespecteerd.
- Resultaten worden gelogd.
- Fouten blokkeren gecontroleerd en zichtbaar.

### US-008 Morning Brief

Als gebruiker wil ik ’s ochtends zien wat Leon heeft gedaan.

Acceptance criteria:
- Brief toont uitgevoerde taken.
- Brief toont wijzigingen/bewijs.
- Brief toont blockers.
- Brief toont approvals die nodig zijn.
- Brief stelt concrete next actions voor.

### US-009 Fan-Control Service

Als gebruiker wil ik dat de chassis fan automatisch reageert op GPU-temperatuur.

Acceptance criteria:
- Service leest GPU-temp.
- Fan speed volgt fan curve.
- Failsafe werkt bij hoge temperatuur/sensorfout.
- Logs zijn beschikbaar.
- Dashboard/status kan tonen of service actief is.

### US-010 Productwaardig Dashboard

Als gebruiker wil ik Leon kunnen bedienen zonder terminal.

Acceptance criteria:
- Dashboard toont workflow, approvals, queue, brief, GPU, fan en routing.
- UI is responsive.
- Foutstates en lege states zijn netjes.
- Controls zijn duidelijk.
- De interface voelt klaar voor dagelijks gebruik.

## Niet-Functionele Eisen

- Betrouwbaarheid: falende subsystemen mogen Leon niet volledig breken.
- Observability: alle belangrijke acties hebben logs/audit entries.
- Veiligheid: risk gates zijn verplicht.
- Kostencontrole: API-gebruik is zichtbaar en geminimaliseerd.
- Lokale-first privacy: lokaal verwerken waar redelijk mogelijk.
- Performance: dashboard blijft bruikbaar tijdens GPU jobs.
- Herstartbaarheid: services herstellen netjes na restart.
- Traceability: Morning Brief moet naar bewijs kunnen verwijzen.

## Release Milestones

### Milestone 1: Baseline Integration

- Bestaande Phase 3 onderdelen nalopen.
- Open gaps in task/queue/brief/autonomy vastzetten.
- Dashboardstatussen koppelen aan echte state.

### Milestone 2: GPU Runtime

- M40 detecteren.
- Ollama valideren.
- `llama.cpp` valideren.
- Benchmark uitvoeren.
- Backend kiezen.
- Modelrouting activeren.

### Milestone 3: Fan Service

- GPU-temp uitlezen.
- Fan-control script/service maken.
- Fan curve instellen.
- Failsafe toevoegen.
- Logging/status toevoegen.

### Milestone 4: Autonomous Daily Workflow

- Chat-to-task.
- Prioritization.
- Safe execution.
- Browser/web research.
- Approvals.
- Night Queue.
- Morning Brief.

### Milestone 5: Product Dashboard

- Alle primaire controls/statussen.
- Approval UI.
- Queue/brief/audit views.
- GPU/fan/routing views.
- Responsive polish.
- Error/empty states.

### Milestone 6: End-to-End Acceptance

- Eén echte taak vanuit chat.
- Eén autonome gekozen taak.
- Eén Night Queue run.
- Eén Morning Brief.
- GPU-route gevalideerd.
- Fan-service actief.
- Approval gate bewezen.

## Belangrijkste Eindtest

Phase 4 is klaar wanneer dit scenario werkt:

Leon kiest zelf een waardevolle taak, gebruikt browser/web research waar nodig, routeert modelwerk goedkoop/stabiel via lokaal of API, voert veilige stappen uit, vraagt approval voor riskante stappen, draait dit eventueel via Night Queue, levert een Morning Brief met bewijs, en toont GPU/fan/modelrouting/status correct in het dashboard.

## Open Beslissingen Voor Implementatie

- Exacte lokale modellen voor M40 24GB.
- Definitieve keuze tussen Ollama en `llama.cpp` als standaard backend.
- Exacte GPU temperature thresholds.
- Exacte fan-control methode afhankelijk van hardware/PWM-toegang.
- Welke browser research tool technisch het stabielst is.
- Definitieve risk-level thresholds per actieklasse.

## Definitie Van Klaar

Phase 4 is klaar als Leon als dagelijks systeem bruikbaar is en de gebruiker alleen nog feedback hoeft te geven op gedrag, prompts, prioriteiten, UI-details en thresholds. Structurele bouwblokken mogen dan niet meer ontbreken.