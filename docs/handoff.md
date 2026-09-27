# Overdracht — Leon / Gaia

**27 september, gezamenlijke GPU-prioriteiten gedeployd:** chat en inkomende
shopperreacties vóór zoeken, achtergrondwerk en coding. Wachttijd verhoogt de
prioriteit zodat oude taken ook starten; lopende generaties worden niet afgebroken.
SQLite bevat uitsluitend tijdelijke procesmetadata; dode/reboot-PID tickets worden
opgeruimd. Echte subprocessproef bevestigt chat vóór achtergrondwerk; echte
coding-wrapper stelt uit met exit75 voor wachtende chat. Generatievrijgave hangt
niet af van een nieuwe databaseverbinding. Workerlease omvat wachten én generatie.
Live chat gaf “Leon is bereikbaar.” via Ollama met charged0. 579 backendtests.
Nog open: adaptieve modelkeuze/batching en Code Worker vanuit chat. Volgende
onderdeel op eigenaarverzoek: echte gesprekreflectie en vaardigheden-todo om22:00.
Google writegrant is op27september inmiddels true; echte writeproef nog nodig.

**26 september, globale M40-temperatuurbewaking gedeployd:**
leon-m40-guard.service is enabled/active met een doorlopend nvidia-smi/NVML-
meetproces voor GPU0 (op deze VM geverifieerd Tesla M40 24GB). Losse NVML-
initialisatieprobes konden hier langer dan acht seconden vastlopen; het vaste
meetproces levert nu iedere seconde een verse meting. Bij >=89C of ontbrekende
metingen stopt alleen Leons eigen Ollama-service; bij <=80C gedurende 30 seconden
kan de bewaker uitsluitend zijn eigen stop hervatten. Monotone tijd voorkomt
verkorten van de afkoelperiode door een klokcorrectie. Een handmatige service-
stop wordt niet automatisch ongedaan gemaakt. Proxmox houdt de fysieke fan.

Backend/worker starten na de bewaker via M40-specifieke systemd-drop-ins. Alle
lokale generatiepaden en de coding-wrapper vereisen een verse passende status.
Bij afkoeling blijft lokaal wachtrijwerk staan zonder retries te verbruiken;
andere lokale checks kunnen door. Queuebereiding gebruikt nu werkelijk zijn
meegegeven LocalModelConfig. Incidenten/resultaat in verenigd Werk (Leon Server)
en gededupliceerde chatmeldingen; onveranderde gezonde metingen blijven stil.
Meldingspoging wordt bewaard en na daemonherstart opnieuw bezorgd.

Echte gecontroleerde foutproef: een onleesbare meting werd gesimuleerd bij een
koele idle GPU; eigen Ollama-stop bevestigd. Eerste herstelproef faalde door
NVML-initialisatiehangs; na wijziging naar continu meten bevestigde de productie-
bewaker de afkoelperiode en eigen serviceherstart. Geen fysieke 89C-stressproef.
Daarna echte chatpreview provider=ollama/reservering0, chatantwoord “Leon werkt
lokaal”, job succeeded/charged0. Guard/Ollama/backend/worker active; verse
metingen onder de grens. 573 backendtests en bash/systemd-controles geslaagd.
Fake-modeltests gebruiken een eigen GPU-lock zodat productie-coding ze niet
blokkeert. Frontend ongewijzigd; eerdere 56 webtests/typecheck/build blijven geldig.

OpenCode/Qwen op de M40 kreeg één kleine read-only review van thermal_guard.py,
met maximaal 120 seconden. De procesgrens werd bereikt na step_start, zonder
verdict of wijziging; dit is geen geslaagde codereview. Lease vrij en GPU idle
na afloop. Niet herhalen zonder de OpenCode-context-/prefillkosten te verbeteren.
Code Worker vanuit chat, schedulerprioriteiten en gezamenlijke nachtverbetering
blijven open. Google write-consent en Docker-groepstoegang blijven eigenaarstappen.

**26 september, echte vrije-momentenplanner:** calendar.find_slots is vanuit
chat aangesloten op volledige Google-events van de primaire agenda. Bestaande
planner-gapberekening wordt hergebruikt zonder sampledata. Overlap, all-day,
nonblocking/cancelled events, grenzen, verleden en Amsterdam-DST zijn afgedekt.
Afgekapt of onbekend resultaat levert geen vrijverklaring. Defaults 09:00–17:00
staan expliciet in het antwoord; overige agenda's zijn niet meegenomen.

Eerste echte chatproef ontdekte een M40-schemafout (datums bij kloktijdvelden).
Het schema is verduidelijkt en de adapter accepteert ook datumkloktijden met
geverifieerde dag/Amsterdam-offset; ontbrekende/onjuiste gegevens geven een
vriendelijke verduidelijking. Vervolgbericht in hetzelfde echte gesprek ging
chat → M40-router → Google → complete met één bevestigd morgenvenster. Geen
agenda-mutatie/Firecrawl/OpenAI-call; direct providerpad ook live bevestigd.
Schrijfrecht blijft ontbreken; de eerder gevraagde extra toestemming staat open.
Samengestelde planning en rekening houden met andere agenda's blijven open.
561 backendtests geslaagd; services active en de feature op de doelserver.
Frontend is ongewijzigd; de vorige 56 webtests/typecheck/build blijven geldig.

**26 september, Calendar-writer gedeployd:** chat ondersteunt eigen afspraken
maken, wijzigen en verwijderen; wijzigingsopdrachten halen actuele Google-events
op zodat echte event-IDs beschikbaar zijn. Amsterdam-tijden inclusief DST worden
gevalideerd. Iedere opdracht krijgt een duurzame identiteit en Planner-taak in
Werk. Ontbrekend consent blokkeert zichtbaar; de worker hervat automatisch na
werkelijke scopegrant en meldt één keer terug in het oorspronkelijke gesprek.
Onzekere uitvoering wordt nooit opnieuw verstuurd; maximaal vijf begrensde
readbacks kunnen de daadwerkelijke Google-toestand alsnog bevestigen.

Persoonlijke primaire-agenda-items zonder gasten of herhaling worden ondersteund;
geen uitnodigingen, gedeelde/terugkerende afspraken of multi-tool-autoplanning.
Wijzigingen gebruiken versiecontrole en worden pas done na providerreadback.
Schrijfrecht is enabled=true maar werkelijk granted=false: actuele accounttoegang
blijft alleen lezen. Vandaag toont de browser-bewezen knop “Afspraken beheren
inschakelen”; aanvullend Google-consent is bij de eigenaar gevraagd. Echte writes
zijn dus nog niet live bewezen. Agenda/Gmail-readprobes na deployment: HTTP200,
0 events en 5 metadata-items (geen persoonlijke inhoud opgeslagen in docs/logs).
Echte M40-routerproef herkende calendar.create en leverde de gevraagde
28 september 14:00–15:00 met +02:00; alleen routing, geen afspraak aangemaakt.
547 backendtests, 56 webtests, typecheck/build geslaagd; lint nul errors/zeven
bestaande warnings. Backend/web/worker herstartten idle en staan active.

**26 september, Werk en klikbare researchbronnen:** agentfilter bevat de
werkelijke Leon-rollen (Research/Server/Writer enz.). Een voltooide taak toont het
bevestigde opgeslagen resultaat, inclusief de echte bronlinks, in plaats van
alleen de ruwe modelcheckpointtekst. HTTPS-links zijn klikbaar in chat én Werk;
geen HTML-rendering van modeltekst. Browserproef Research + Afgerond: precies één
researchkaart, bronnenlabel en drie HTTPS-anchors. Companion naar vrije
headerruimte verplaatst; browserbounding-boxes bewijzen geen overlap met de
opdrachtknop. Typecheck/build en 55 webtests geslaagd; lint nul errors/zeven
bestaande warnings. Tijdelijke browserauthfile is na controle verwijderd.

**Google is nu werkelijk verbonden:** actuele serverstatus configured=true.
Echte geauthenticeerde Calendar-preview voor de komende week slaagt (nul
gebeurtenissen); Gmail-metadata-preview levert vijf echte items. Geen persoonlijke
inhoud in logs of repository. De planner kan nu lezen; afspraken toevoegen,
wijzigen en verwijderen vereist nog de writerintegratie en aanvullend consent.
Docker-groep is nog leeg, dus coding-testsandbox blijft zonder hosttoegang.


**26 september, gedeelde GPU-beurt en zuinigere routing:** gewone chat telt
een gecachet eigen Qwen-model niet langer als bezet. /api/ps toont residentie,
geen generatie; daadwerkelijk gebruik wordt door een gedeelde flock bewaakt.
Alle lokale transportcalls (chat/router/shopper/tasks) delen één lease; de M40-
coding-wrapper gebruikt dezelfde inode en weigert starten bij bezetting. Een
bezet slot wordt begrensd afgewacht; fouten geven de lease altijd vrij. Een
ander resident model of onleesbare status blijft conservatief bezet. Bestaande
Ollama heeft al NUM_PARALLEL=1 en MAX_LOADED_MODELS=1.

Echte warme chatpreview: local_busy=false, provider=ollama, reservering=0.
Echte wrapperproef met gehouden Python-lease: exit75, coding niet gestart;
lease na afloop vrij. 529 backendchecks; bash-syntaxcontrole geslaagd. De
89C-codingguard blijft behouden. Gezamenlijke prioritering en een globale
thermische watchdog voor alle lokale calls blijven nog open.


**26 september, echte serveragent:** wekelijkse zondagcontrole om 10:00
Europe/Amsterdam actief via leon-server-watch.timer. Vaste OS-probes controleren
Leon backend/web/worker/Ollama, vrije schijf en M40-temperatuur. Alleen eigen
backend/web/worker kunnen gericht herstarten, maximaal één poging per service
per zes uur; herprobe bewijst de eindstatus. Ollama wordt niet automatisch
herstart, en een hete/onleesbare GPU verhindert automatische workerherstart.
Geen algemene shelltool vanuit chat. server.status/check zijn aangesloten op
het vaste lokale toolpad.

Routine-uitvoering verschijnt met eigenaar/resultaat in verenigd Werk. Alleen
nieuwe problemen, herstel of een herstelpoging maken een duurzaam gededupliceerd
bericht in Leon updates; stabiele checks sturen geen chatmelding. De echte
herstelproef stopte de idle worker, waarna de serveragent hem aantoonbaar
herstartte: alle vier services active, M40 36C, taak done. Proefmeldingen waren
uitgeschakeld. Eerste gezonde wekelijkse run uitgevoerd, volgende zondag
27 september 10:00 Amsterdam. Browser bevestigde twee afgeronde serverkaarten
met Leon Server, werkelijk resultaat en temperatuur. 521 backendtests,
typecheck/build geslaagd; lint nul errors/zeven bestaande warnings.
De chatstatus-proef vond ontbrekende recovery-metadata bij read-only status;
describe accepteert nu beide vormen en heeft een extra regressietest.


**26 september, geïntegreerde webresearch:** expliciet onderzoek vanuit chat
roept de bestaande Firecrawl search-only connector aan en zet de brongegevens
op de lokale M40-wachtrij. Geen OpenAI-synthese. Resultaat krijgt de daadwerkelijk
gevonden bronlinks in chat en Werk. Zoeksnippets worden als onbetrouwbare data
behandeld; geen claim dat volledige paginas zijn gelezen. Sensuele research
wordt niet naar Firecrawl verstuurd. Dagbudget blijft gedeeld met de bestaande
research-API; budget op/fout geeft een concrete melding zonder automatische retry.

Echte chat → router → Firecrawl → M40 → done-task → terugbezorging bewezen:
1015 tekens en drie echte bronlinks. Twee live searchproeven samen vier credits,
vandaag nog zes beschikbaar. Backend 515 tests, web 55 tests geslaagd;
productiebuild/typecheck eerder deze wijzigingsronde geslaagd. Extra GPT-OSS/M40 read-only codecontrole
stopte na 180 seconden zonder reviewresultaat (alleen glob); model daarna
ongeladen voor normale chat. Niet als geslaagde coding-review meetellen. Google-consent en Docker-toegang zijn
nog eigenaarstappen; daarop wachten houdt andere onderdelen niet tegen.


**26 september, automatisch geheugen in gewone chat:** relevante actieve
geheugenitems en maximaal drie voorkeuren gaan nu mee in de begrensde prompt.
Verwijderde, verlopen, kandidaat- en conflicterende items worden uitgesloten.
De selectie gebeurt in dezelfde SQLite-transactie, zonder tweede schrijf-lock.
Persoonlijke geheugencontext blijft verplicht op de lokale M40; veranderde
context maakt een oude preview ongeldig. Drie regressies + bestaande chat/task-
checks: 27 geslaagd. Geen automatische opslag van alle gesprekken toegevoegd.


**26 september, persoonlijke achtergrondtaken en researchbudget:** gewone
schrijf-, plan- en analysetaken vanuit chat draaien daadwerkelijk via de M40-
wachtrij. Resultaten worden eenmaal terugbezorgd in het oorspronkelijke gesprek
én getoond in verenigd Werk. Pauzeren/hervatten/annuleren via chat aangesloten;
expliciet “later” bewaart alleen, achtergrondopdrachten worden gestart. Echte
M40-checklistproef leverde drie chatberichten en een afgeronde taak. Geen externe
acties of feitenverificatie claimen bij zulke teksttaken. Volledige backend 508
checks geslaagd; web typecheck/build, lint nul errors/zeven bestaande warnings.

Eigenaar autoriseerde maximaal 10 bestaande Firecrawl-credits per Amsterdam-dag.
Duurzame atomische reservering rekent 2 credits per search-only poging; fouten
houden de reservering en dezelfde preview kan niet opnieuw betaald zoeken.
Bestaande providerbalans wordt vooraf gelezen; geen billing/recharge-endpoints.
Live call: drie docs.python.org-bronnen, creditsUsed=2, vandaag 8 over. Bron:
https://docs.firecrawl.dev/features/search#cost-implications. Chatresearch en
M40-synthese blijven de volgende integratiestap. Nieuwe HTTP-budgettest dekt
het doorgeven van de serverconfiguratie; nog apart draaien.


26 september, chat/werk/Google: alle echte opdrachten samen in inklapbaar Werk,
met filters en progressiebolletjes; aparte Shopper-tab en voorbeeldschakelaars
verwijderd, Vandaag compact. M40-chatrouter bedient bounded shopper-/Google-/
geheugentools met duurzaam geen-dubbele-uitvoering-register. Gezamenlijke echte
zoekronde MP+Vinted: 29 advertenties, geen passende 128GB-set, 64GB-contact blijft
op pauze. Google PKCE-callbacks voor vaste HTTPS-host én actuele Quick Tunnel;
LAN-start verhuist eerst naar HTTPS met eigen Leon-login. Eigenaar voegt tweede
callback toe; echte Google-consent/Agenda-call nog open. DuckDNS extern twee
HTTP 200-metingen, thuis NAT-loopbackprobleem: lokale IP of HTTPS-tunnel gebruiken.
501 backendtests, 55 webtests, typecheck/build geslaagd; lint nul errors/zeven
prototype-warnings. Zie `docs/chat-work-google.md`.


Stand: **25 september 2026**. De gebruiker wil vooral coderen; houd deze overdracht kort.

## Nieuwste wijziging

26 september, voorkeur 128GB: bestaande 64GB-conversatie `on_hold`; geen
antwoord/afwijzing verstuurd. Wekelijkse watch blijft actief, nu minimaal 128GB
voor 21 dagen, daarna 64GB als reserve. Dit bestaande gesprek blijft ook daarna
op pauze tot nieuwe owner-instructie. Nieuwe echte zoekronde: 28 advertenties,
geen passende 128GB-set. Dashboard toont de deadline en het gepauzeerde gesprek;
regressies bewijzen uitstel van fallback en geen reply aan held-contact.

26 september, correctie eigenaar: nieuwe openingsbiedingen worden verplicht
onder de vraagprijs gezet, met verhouding voor alleen de gewenste modules.
EUR45 voor vijf wordt EUR30 voor vier; EUR45 voor vier wordt EUR35. Merk tussen
hoeveelheid en GB wordt herkend. Kortere losse toon zonder formele slotzinnen.
Het bestaande EUR45-bericht blijft onaangetast; deze wijziging geldt voor nieuwe
contacten. Zie de openingsstrategie in `docs/shopper-worker.md`.

26 september: Leon heeft nu een eigen shopper-worker op de M40, duurzame
wekelijkse zoekopdrachten en een geauthenticeerde `/shopper`-pagina. De eerste
DDR3 ECC-watch (64–128GB, vier slots, totaal < EUR50) doorzocht live Marktplaats;
Qwen koos zelfstandig een 64GB-kandidaat en een totaalbod. User-systemd timer
actief; backend/web gedeployd. Eerste contact via het vertraagde advertentiedialoog is live bevestigd: Leon
verstuurde zelf een bericht en las exact dat eigen bericht terug in het nieuwe
gesprek. Geen aankoop/acceptatie gedaan.
483 backendtests en 51 webtests; 33 nieuwste shopperregressies geslaagd; typecheck/build geslaagd, lint
nul errors/vijf bestaande warnings. Nieuwe gerichte regressies slagen.
Server-headless Chrome op CDP 9223 vervangt de Mac; eigen Marktplaats-login
bevestigd na private overdracht van uitsluitend marketplace-sessies. De gebruiker
kan de Mac-browser/tunnel sluiten. DOM-inboxlistener draait als systemd-service;
geen vijfminutenpoll. Reacties gepland met 15–45 minuten vertraging binnen
08:00–23:00 Europe/Amsterdam; nachtberichten wachten tot ochtend. Counteroffers,
vragen, vriendelijk afwijzen en owner-ready status zijn aangesloten voor
bevestigde gesprekken. Duurzame claims, superseding en owner-cancel getest.
Eerste-contactbezorging bevestigd; echte inkomende meldingsbezorging nog onbewezen;
Vinted-berichten/ticketmonitor open. Compact toonprofiel blijft privé.
Zie [shopper-worker](shopper-worker.md) en [browser-MCP](marketplace-browser-mcp.md).

Gaia Vandaag heeft een live alleen-lezen weerkaart voor vast Amsterdam via
Open-Meteo. Backend en web valideren een begrensd contract; alleen één vaste
HTTPS-host, 64 KiB antwoord, drie dagen en tien minuten cache zijn toegestaan.
Bron/licentie zijn zichtbaar en iedere poging wordt geaudit. Een echte call op
de doel-VM, daaropvolgende cache-hit en geldige auditketen zijn bewezen. De
volledige stand is 448 backendtests, 51 webtests, TypeScript, productiebuild en
lint met nul errors/vijf bestaande warnings. Zie [weerconnector](weather-readonly.md).

Tijdens de volledige suite bleek de bestaande preflight te kunnen crashen als
`nvidia-smi` zelfs na SIGKILL ononderbreekbaar bleef. Die tweede timeout wordt
nu begrensd als probe-fout gerapporteerd; de gerichte regressieset slaagt.

De verbonden chat is nu een echte chat: nieuwe gesprekken worden direct
aangemaakt en lokale M40-beurten worden zonder extra checkbox verzonden. Een
lokale classificatie markeert sensuele tekst en forceert Ollama; normale tekst
kan bij een actief Ollama-model naar de geconfigureerde OpenAI-fallback. De
providerkeuze wordt aan de aanvraag gebonden. Stand: 448 backendtests en 51
webtests.

Op 25 september zijn de door de gebruiker aangeleverde Firecrawl-key en
Google OAuth-client veilig in `.env.local` gezet. Firecrawl staat aan met een
expliciete domeinallowlist en de live status meldt configured. Google staat
aan, maar blijft fail-closed tot de gebruiker de OAuth-flow afrondt en een
access/refresh-token met Agenda- en Gmail-read-only scopes heeft.

## Doelserver nu

Leon draait lokaal als user-systemd-services: Ollama, backend, worker, web,
Caddy, router/DuckDNS-timer, tijdelijke tunnel en autonomietimer. Publieke
HTTPS via `https://leon-ai-assistant.duckdns.org` is van buitenaf beproefd.
Registratie vraagt een eenmalige code uit `.runtime/leon-web-setup-code` en
laat de gebruiker zelf een wachtwoord kiezen; het productieaccount is
geregistreerd en tokenlogin is uit de webflow verwijderd. Zie [publieke toegang](public-access.md). De M40-chatroute (`qwen2.5-coder:14b`) is via browser, API,
SQLite-worker en GPU end-to-end beproefd; OpenAI blijft uit. De lokale
OpenCode-coding-agent gebruikt `gpt-oss:20b`; echte `read`- en `edit`-tools zijn
op een wegwerpbestand bewezen, met 80C piek in de schrijftest. Setup is
`./scripts/leon-m40-coding-setup`, start is
`./scripts/leon-m40-coding-agent`. De gebruiker koos 89C als afslag; dat is
ook de driververtragingstemperatuur. Proxmox regelt de fysieke fan buiten de
VM; het hostscript en RPM zijn vanuit hier niet verifieerbaar. Zie
[M40-bewijs](m40-deployment-evidence.md).

De algemene assignmentflow gebruikt nu eveneens een echte duurzame,
text-only `local_ollama`-run op de M40. Een geïsoleerde productie-equivalente
proef eindigde in `waiting_for_review`, met nul providerkosten, geldige
auditketen en 71C piek. Cold-startleases, dubbele apply en herstel tussen
assignment/apply en queue-insert hebben regressietests. Stand: 448 backendtests,
51 webtests, typecheck en productiebuild. Doelserver-preflight en de
geïsoleerde delivery-smoke zijn nu ook geslaagd; zie
[doelserverbewijs](server-preflight-evidence-2026-09-25.md). Open:
Google/Firecrawl-accounts en self-improvement-testcontainer ontbreken, plus
brede productacceptatie en publicatie van deze serverwijzigingen. Nieuwe wijzigingen eerst testen,
draaiende services herstarten en veilige bron naar GitHub synchroniseren.

## Lopende aanvulling

- 14 september: fail-closed rootless Podman-uitvoerkern toegevoegd en aan de
  self-improvement API/Gaia gekoppeld. Contract vereist immutable image/base commit,
  root-owned stabiele Podman-binary, eigen niet-root serviceaccount, lokale
  rootless cgroup-v2/seccomp-host, vaste netwerk/proxy/filesystem/process/resource-
  grenzen en non-root smoke-run. Alleen descriptor-veilig gelezen bestanden
  worden als private read-only snapshots gebonden; output wordt tijdens proces
  op 64 KiB begrensd en secret-geredigeerd; iedere containernaam krijgt bewezen
  cleanup. Stand: 15 sandboxtests; volledige backend 368 tests + twee subtests,
  46 webtests, typecheck/build/lint. Python-, security-, React- en TypeScript-
  herreviews zonder resterende P1/P2.
  API en Gaia binden inmiddels execution mode, policyhash en imagecommit vóór
  approval; configwijziging invalideert uitvoering, resultaten bewaren alleen
  sanitized hashes/status. Static blijft default. Open: digest-gepinde
  Linux-image bouwen, config voor doelserviceaccount, Ubuntu-probe/isolatiebewijs
  en browserbewijs met beide modi. Zie
  [OS-sandbox](os-sandbox.md).

- 13 september: Gaia Werk-bediening voor review-only self-improvement gereed.
  Ingeklapte operatorflow bewaart patch alleen in componentstate, maakt exacte
  preview, wist preview/checkbox na edit en gebruikt apart scoped atomisch
  approve-endpoint vóór run. Browserketen bewees preview → invalidatie → nieuwe
  preview → approval → statische review, zonder bronmutatie of achtergebleven
  tempmap. Stand: 345 backendtests + twee subtests, 46 webtests,
  TypeScript/build/lint; Python/security/React-review zonder P1/P2. Zie
  [browserbewijs](self-improvement-browser-evidence.md).

- 13 september: geauthenticeerde tweestaps self-improvement-API gereed. Preview
  maakt uit een vaste bronroot een schone tijdelijke Git-repository en exacte
  R3-approval; run verbruikt die approval atomisch en voert alleen statische
  review uit. Een uur expiry/cleanup, concurrency, symlink-/rename-races,
  secretblokkade en HTTP-keten getest. Geen raw patch of paden in publieke
  state; gewijzigde code draait nooit. Stand na Gaia-koppeling: 345 backendtests
  + twee subtests; Python- en security-review zonder P1/P2. OS-sandbox en echte
  patchtests blijven open. Zie [sandboxgrens](self-improvement-sandbox.md).

- 13 september: lokale agentrun-review sluit nu oudertaaklevenscyclus. Acceptatie
  beweegt `new/planned/active` via geldige transities atomisch naar `review` en
  bewaart begrensde runprovenance. Afwijzing en wijzigingsverzoek veranderen
  taakstatus niet; dubbele review schrijft niets; `review → done` blijft een
  aparte expliciete stap. Onbeperkt bewijs wordt niet geparseerd of gekopieerd.
  Stand: 332 backendtests + twee subtests; Python-review zonder P1/P2. Zie
  [agent runtime](agent-runtime-adapter-implementation.md).

- 13 september: geauthenticeerde read-only servermonitor en Gaia-kaart gereed.
  Alleen begrensde aggregaten en vaste schijflabels; geen logs, secrets,
  caller-paden, commando's of achtergrondprobe. Connectoraudit en uit-schakelaar
  getest. Stand: 328 backendtests + twee subtests, 42 webtests, TypeScript,
  productiebuild en lint zonder fouten. Browser: laden en verversen geslaagd op
  tijdelijke fixture; geen absolute paden zichtbaar. Zie
  [servermonitor](server-monitor.md) en [browserbewijs](server-monitor-browser-evidence.md).

- 13 september: veilige self-improvement kern toegevoegd. Alleen exact gebonden,
  eenmalig goedgekeurde patches in system-temp Git-repositories; statische Git-
  en Python-syntaxcontrole, rollbackbewijs, geen uitvoering van gewijzigde code.
  Git clean-filter exploit uit review gerepareerd en met markerregressie bewezen.
  De latere HTTP-koppeling en crashcleanup staan hierboven. Volledige
  self-improvement blijft open tot OS-sandbox, echte tests en Gaia-integratie.
  Zie [sandboxgrens](self-improvement-sandbox.md).

- 12 september: begrensde Firecrawl v2 search-only executor en Gaia Research-
  kaart lokaal gereed, standaard uit. Preview-ID/fingerprint is server-side
  gebonden en verloopt na 15 minuten; auth, caps, domein/IP-filter en provider-
  outcomeaudit getest. Browser toont disabled-state eerlijk en blokkeert start.
  Stand: 314 backendtests + twee subtests, 39 webtests, TypeScript/build, lint
  nul fouten. Live Firecrawl-call/key/budget blijft open. Zie
  [research](research-executor.md) en [browserbewijs](research-browser-evidence.md).

- 12 september: bestaande nachtqueue, value scoring en ochtendbrief gekoppeld
  aan Gaia. Veilige vaste bronscan werkt handmatig en via optionele 22:00-
  systemd-timer; geen provider/netwerk of memory/task/cache-mutatie. Browser:
  run → ochtendbrief → herladen → opnieuw verbinden → zelfde bewijs. Volledige
  stand: 305 backendtests + twee subtests, 35 webtests, TypeScript/build, lint
  nul fouten. Zie [autonomiebewijs](autonomy-browser-evidence.md).

- Chat/installatie is gepubliceerd op `codex/complete-leon`: GitHub-commit `851d9880`, exact dezelfde bronboom als lokale `6fa2150` (`d05dd52a`).
- Vandaag/Memory zijn lokaal afgerond in commit `2bdb5d4`. Backend: 299 tests
  plus twee subtests geslaagd. Web: 30 tests, TypeScript, build en lint zonder
  fouten geslaagd. Browser: tokenherstel, bewaren, herladen, zoeken, inline
  corrigeren, verwijderen met verplichte reden en 1280×720-indeling geslaagd op
  tijdelijke SQLite. Zie [acceptatiebewijs](memory-today-browser-evidence.md).
- Google Agenda/Gmail is door gebruiker gekozen als eerste alleen-lezen
  koppeling. Begrensde client, geauthenticeerde serverroutes, Gaia-preview,
  gerichte tests en onafhankelijke reviews zijn afgerond. Browseracceptatie met
  synthetische data bewijst klikgestuurde Agenda/Gmail-metadata, bronverwijzing,
  herlaadgedrag, DST-grenzen en 1280x720-indeling. Preview schrijft geen mail- of
  agendagegevens naar lokale opslag. Accountverbinding en live acceptatie zijn
  nog niet gereed. Zie [Google alleen-lezen client](google-readonly.md) en
  [browserbewijs](google-browser-evidence.md).
- Kosten: vervolgcoördinatie is ingesteld op `gpt-5.6-sol` (medium). Gebruik smalle opdrachten, bewaar ruimte voor verificatie en controleer gedeeld limiet vóór nieuw groot werk. Het volledige productdoel blijft actief.

## Nieuwste werk

- Volledige lokale installatieproef geslaagd: setup → start → beide
  geauthenticeerde API-verzoeken HTTP 200 → doctor → online backup → stop →
  restore. Marker en SQLite-integriteit behouden; alle drie eigen
  procesgroepen beëindigd. Eerdere 401 was deels onjuiste tokenparsing in
  testscript; echte seed-race, procesherkenning en poortuitwijking zijn ook
  hersteld. Herhaal met `./scripts/leon-delivery-smoke`; zie
  [delivery-evidence.md](delivery-evidence.md).

- Verificatie 9 september: **269 backendtests + twee subtests**, **19 webtests**,
  TypeScript en build geslaagd. Lint: nul errors, vijf bestaande warnings.
  Pakketupdates plus een gerichte sharp-override brengen npm audit op nul
  kwetsbaarheden. Browser: preview blijft tijdens polling behouden; gewijzigde
  tekst trekt approval in; nepantwoord en geschiedenis overleven herladen;
  tweede beurt gebruikt zichtbaar goedgekeurde eerdere context.
- Lokale setup/start/stop/doctor en SQLite-backup/restore toegevoegd. Backend
  en worker krijgen dezelfde configureerbare private DB; web krijgt het juiste
  backendadres bij aangepaste poort. Ubuntu-systemdvoorbeelden zijn aanwezig,
  maar niet geïnstalleerd of op Ubuntu/M40 getest. Zie [installatie](installation.md).

- 9 september: duurzame Chat en Gaia-koppeling toegevoegd op `codex/complete-leon`.
  Exacte context/output-/kostenapproval, aanvraagdeduplicatie en herstel staan
  in [chat.md](chat.md). Werk kan oudere jobs rechtstreeks op ID herstellen.
  Hervatwatch gebruikt expliciete FIFO-collectoren en werkt ook met Bash 3.2.
  De oudere updates hieronder beschrijven hun eigen meetmoment.

- Actuele werkkloon op Mac: `/Users/perhorstmanshoff/.codex/worktrees/leon-completion-20260908`.
  Gedeelde oorspronkelijke SSD-map niet overschrijven; daarin ontbreken
  kernbestanden en `git diff` meldde een onleesbaar object. Deze kloon start vanaf
  actuele GitHub-main `0bc67c6`. De kostenvoorkeur is expliciet: lichte agents,
  compacte opdrachten en hoofdagent voor integratie/review.

- Kostenherstel werkt met eerder ontvangen, gevalideerde usage-receipts. Gaia toont tokens/bedrag en vraagt aparte approval; de transactie boekt uitsluitend kosten af. Taak/checkpoint worden niet geslaagd gemaakt, geen nieuwe providercall. Timeout zonder bruikbaar verbruik blijft geblokkeerd. Late workers en dubbele approvals kunnen de afboeking niet terugdraaien of verdubbelen.
- Gaia-Werk heeft nu tekstinvoer, lokale kostenpreview en een niet-vooraf aangevinkte approval. Wijzigingen wissen eerdere approval. Alleen een aanvraag-UUID wordt tijdelijk in sessionStorage bewaard voor een onzekere verzending; herstel zoekt zonder opnieuw te verzenden. Het modelantwoord is leesbaar buiten de ruwe bewijsweergave.
- Begrensde OpenAI-tekstuitvoering toegevoegd aan dezelfde WorkQueue: expliciete tekst-/kostenapproval, vaste Responses-endpoint, geen tools/retries, transactionele reservering vóór verzenden en resultaatopslag vóór checkpoint. Onzekere uitkomst blokkeert nieuwe calls en wordt niet automatisch herhaald. Zie [modeluitvoering](model-work.md).
- Sleutel lokaal aanwezig, maar geen live calls of echte budgetinstellingen gedaan. Worker ondersteunt expliciet `--env-file .env.local`; alleen key aanwezigheid activeert niets. Op expliciet verzoek sleutelachtige waarde uit `.env.example` verwijderd; `.env.local` hash-identiek gebleven. Overige voorbeeldwijzigingen van de gebruiker blijven lokaal/buiten de commit.

- Volledige SSD-bron hersteld; actuele server/store/tests geïntegreerd, inclusief ongecommitte serverwerk.
- Nachtqueue fabriceert geen succesvolle patches of testuitslagen meer, ook niet na R3-toestemming.
- Nieuwe echte lokale worker: `work_queue.py`, `local_worker.py`, `work_api.py`. SQLite-checkpoints, unieke request-id, lease/fencing, pauze/hervatten/annuleren, maximaal drie pogingen per onderbroken stap.
- Gaia-Werk gebruikt echte backendstatus. De oude demo blijft expliciet apart; geen fictieve ETA. Website en backend draaien lokaal op Node/Python; Cloudflare-demo is opt-in.
- Python-syntaxcontrole met bronhashes blijft werken. Modeltransport is offline geïntegreerd/getest, **nog geen live betaalde call, algemene LLM-agent of autonome codewijziging**.
- Bestaande hervatwatch gerepareerd: wacht op beide uitvoercollectoren vóór classificatie; stdout/stderr blijven gescheiden.

## Verificatie

Nieuwste kostenherstel: 253 backendtests + twee subtests en 16 webtests geslaagd;
TypeScript/build geslaagd, lint nul errors/vijf bestaande warnings. Desktopbrowser
met nepantwoordfout: onzeker → verbruiksbewijs → lege approval/verzendknop uit →
goedkeuren → reservering nul, verbruik vastgelegd, opdracht blijft onafgerond 0/1.

Eerdere UI-koppeling: 238 backendtests + twee subtests en 14 webtests geslaagd;
TypeScript/build geslaagd, lint nul errors/vijf bestaande warnings. Browser:
preview → approval vervalt na edit → opnieuw goedkeuren → afgerond 1/1 met
leesbaar nepantwoord → herladen en opnieuw verbinden → hetzelfde antwoord.
Geen betaalde API-aanroep. Details in [model-work.md](model-work.md).

Zie [uitvoering en testbewijs](local-work.md). Browserketen getest met tijdelijke SQLite en nepcredential: taak maken → wachtrij → pauze → hervat → 1/3 checkpoint → pagina herladen → hetzelfde checkpoint → afzonderlijke workerprocessen → afgerond 3/3. Geen private recoverydatabase gebruikt.

## Volgende codewerk

1. Google-account via private credential-provider verbinden en kleine
   live read-only acceptatie uitvoeren. Side-effecting tools hebben een eigen
   backendapproval-/idempotentiecontract nodig. Voer daarna één kleine live
   Firecrawl-search uit met gekozen budget en allowlist.
2. Netwerkuitkomsten zonder verbruiksbewijs blijven geblokkeerd; toekomstig extern bewijs mag alleen met betrouwbare aanvraagkoppeling worden verwerkt. Geen handmatig verzonnen bedrag of automatische betaalde retry. Live kleine call pas met gekozen budget en expliciet gedeelde tekst.
3. Ubuntu-installatie/systemd, private backup/restore en doelhardware meten zodra de server beschikbaar is.

Store (~8.400 regels), server (~4.450) en oorspronkelijke tests (~5.150) blijven groot. Nieuwe verantwoordelijkheden in eigen modules houden, server alleen koppelen; geen brede refactor zonder relevante tests.

## Bron, privacy en synchronisatie

Werkkloon: `C:/Users/perhorst/Documents/ChatGPT/New project/leon-ai-assistant`.
Volledige ongewijzigde private recovery: `C:/Users/perhorst/Documents/leon-ssd-full-2026-09-06`.
Server-HEAD: `6b1863b6e1fdc612672c816ac048313c677115ca`, 16 lokale commits plus dirty werk. Alle reguliere kopiehashes en Git-objecten gecontroleerd. Archief bevat credentials; nooit publiceren. Database is gekopieerd, geen live restore geclaimd.

`codex/ssd-recovery-2026-09-06` blijft de historische gedeeltelijke snapshot. De ontwikkelbranch `codex/night-queue-evidence` verenigt die bron met de actuele main-overdracht. Originele servergeschiedenis/private logs worden niet gepusht. Zie [WSL-bewijs](wsl-recovery.md) en [historische audit](server-recovery-audit.md).

Doelserver-readiness is nu gemeten: Ubuntu x86_64, Tesla M40 24GB, driver
580.178.04, 10 CPU-threads en ongeveer 9.3 GB RAM zichtbaar. De eerdere
16-GB-aanname was onjuist en is vervangen door deze meting. Nog open: Podman-
installatie en sandboxacceptatie, live Google/Firecrawl-providers, financiële/
communicatie/installer-approvalketens, overige connectors en volledige
productacceptatie. Phase-4-stories zijn niet afgevinkt op basis van mocktests.

Voor hervatten op de server: controleer HEAD/branch/dirty werk en gebruik bij twijfel een nieuwe kloon; overschrijf de oorspronkelijke bron of database niet. GitHub is de code-/planoverdracht, geen backup van lopende processen of gesprekken.
