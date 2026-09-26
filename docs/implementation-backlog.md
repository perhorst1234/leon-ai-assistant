# Leon / Gaia — uitvoeringsbacklog

**26 september, shopper:** eigen Leon-worker, M40-selectie, duurzame wekelijkse
watch en `/shopper`-bediening gedeployd. Eerste DDR3 ECC-watch live gezocht en
lokaal door Qwen beoordeeld. Contact via zichtbare Marktplaats-dialoog aangesloten;
geen aankoopflow. Serverbrowser en private Marktplaats-sessie live bevestigd; Mac niet meer nodig.
DOM-meldingstrigger + duurzame vertraagde replies aanwezig (15–45 minuten,
08:00–23:00 Amsterdam), lokale counteroffers/vragen/afwijzing en owner-ready
status. Eerste echte Leon-contactbezorging via de serverbrowser bevestigd door
teruglezen van het eigen bericht. Volgende: echte inkomende notificatie en
vertraagd antwoord end-to-end bewijzen; daarna Vinted-berichten en TicketSwap-eventmonitor. Zie `docs/shopper-worker.md`.

**25 september, chat en live weer:** Gaia's verbonden chat toont na verzenden
zichtbaar de reviewkaart en scrollt daar automatisch naartoe; de demo-toast wordt
alleen nog in het ontwerpvoorbeeld gebruikt. Leon blijft in chat compact naast
de kop staan. Daarnaast gebruikt Gaia Vandaag nu een echte alleen-lezen
Open-Meteo-call voor vast Amsterdam. Host, locatie, velden en drie dagen staan
server-side vast; antwoord is maximaal 64 KiB, wordt dubbel gevalideerd, tien
minuten gecachet en volledig via de connectoraudit gevolgd. Bron en CC BY 4.0
staan in de kaart. Echte call plus cache-hit en geldige auditketen zijn op de
doel-VM bewezen. Volledige stand: 448 backendtests, 51 webtests, TypeScript,
productiebuild en lint met nul errors/vijf bestaande warnings. Zie
[weerconnector](weather-readonly.md). Google/Firecrawl-credentials en de
self-improvement-doelcontainer blijven open.

**25 september, publieke website:** `https://leon-ai-assistant.duckdns.org`
heeft een geldig certificaat en extern HTTP 200. De webapp vraagt bij eerste
gebruik om een eenmalige instelcode en een zelfgekozen wachtwoord, daarna om
alleen het wachtwoord. Het productieaccount is geregistreerd. Routerlease,
DuckDNS en TLS worden door user-systemd onderhouden. Geïsoleerde registratie-
en loginflow, API-toegang en browserweergave zijn getest; zie
[publieke toegang](public-access.md). LAN NAT-loopback ontbreekt vermoedelijk;
de tijdelijke tunnel is beschikbaar als fallback. Google/Firecrawl-accounts en de
self-improvement-doelcontainer blijven de eerstvolgende productstappen.

Dezelfde dag rapporteerde de read-only doelserver-preflight een Tesla M40 24GB,
driver 580.178.04, 10 CPU-threads en 9.3 GB RAM. De geïsoleerde delivery-smoke
doorliep setup, auth, doctor, backup, stop en restore met geldige SQLite-
integriteit. Zie [doelserverbewijs](server-preflight-evidence-2026-09-25.md).

**21 september, doelserver:** de lokale user-systemd-units draaien. Chat via
Ollama/Qwen 14B op de Tesla M40 is end-to-end bewezen; OpenCode/GPT-OSS 20B
heeft echte file read/edit/readback uitgevoerd met 80C piek. M40-coding-agent
en pinned setup staan in `scripts/`. De 89C-afslag is gebruikerskeuze, geen
duurproef; Proxmox-fan-RPM is vanuit de VM onbekend. Zie
[M40-bewijs](m40-deployment-evidence.md). Echte geautoriseerde text-only
agent-runs gebruiken nu dezelfde duurzame Ollama-wachtrij; de echte M40-proef
bleef op 71C en eindigde reviewbaar. Volgende productstap: connectoracceptatie,
self-improvement-sandbox en volledige scenario's.

**14 september, OS-sandboxkern:** fail-closed rootless Podman-contract toegevoegd
en aan self-improvement API/Gaia gekoppeld. Immutable image en exact base commit,
root-owned executable/inode, lokale rootless cgroup-v2/seccomp-probe, vaste
network/proxy/image-volume/filesystem/process/resourcegrenzen en non-root smoke
zijn verplicht. Workspacepaden worden niet gemount: toegestane bytes gaan via
descriptor-veilige reads naar private read-only snapshots. Output is tijdens
uitvoering begrensd en geredigeerd; cleanup is verplicht voor succes. 15 gerichte
sandboxtests en volledige backend 368 tests + twee subtests, 46 webtests,
typecheck/build/lint geslaagd. Reviews zonder resterende P1/P2. API/approval en Gaia binden nu exact execution
mode, policyhash en imagecommit, met durable sanitized testbewijs; static blijft
default. Open: Podman ontbreekt op de doel-VM; doelimage bouwen/pinnen,
Ubuntu-hostacceptatie en browserbewijs
voor static/Podman-modi. Zie [OS-sandbox](os-sandbox.md).

**13 september, agenttaaklevenscyclus:** geaccepteerde lokale agentruns brengen
hun oudertaak atomisch via geldige statusovergangen naar `review`, met begrensde
runprovenance. Afwijzingen blijven actiegericht, review is eenmalig en `done`
vereist nog expliciet resultaat plus verificatienotitie. Oversized bewijs wordt
niet geparseerd. 332 backendtests plus twee subtests en onafhankelijke Python-
review geslaagd. Echte provideruitvoering en capability-isolatie blijven open.

**13 september, servermonitor:** read-only `GET /api/server/status`, connector-
audit en Gaia-kaart toegevoegd. Endpoint accepteert geen caller-paden of
commando's en toont alleen begrensde OS-, uptime-, load-, geheugen-, vaste
schijflabel- en processtatus. Uitgeschakeld betekent geen probe. 328 backendtests
plus twee subtests, 42 webtests, TypeScript/build/lint en lokale browserproef
geslaagd. Doelservermeting en muterende beheeracties blijven open. Zie
[servermonitor](server-monitor.md) en [browserbewijs](server-monitor-browser-evidence.md).

**13 september, self-improvement kern:** geauthenticeerde preview/run-API rond
review-only patchvalidator toegevoegd. Exacte R3-approval bindt opaque tijdelijke
repository, base commit, patchhash, filelijst en statische validatie en wordt
atomisch één keer verbruikt. Een uur expiry/cleanup, concurrentie en
descriptor-relatieve symlink-/renamebescherming zijn getest. Geen gewijzigde
code wordt uitgevoerd; publieke state bevat geen raw patch of paden. Gaia Werk
heeft nu ingeklapte exacte preview/checkbox/run-bediening; browserproef
bevestigt invalidatie na edit, reviewbewijs, bronbehoud en cleanup. Volledige
stand: 345 backendtests plus twee subtests en 46 webtests; Python-, security- en
React-review zonder P1/P2. Volledige self-improvement blijft open tot OS-sandbox,
echte tests en gecontroleerde nachtqueue-integratie aantoonbaar werken. Zie
[sandboxgrens](self-improvement-sandbox.md) en
[browserbewijs](self-improvement-browser-evidence.md).

**12 september, research:** Firecrawl v2 search-only executor, vaste host,
HTTPS/domein/IP-filter, caps, server-side preview-ID/fingerprint met 15 minuten
geldigheid, provider-outcomeaudit en Gaia tweestapsflow toegevoegd. Standaard
uit; geen live call of sleutel gebruikt. 314 backendtests plus twee subtests,
39 webtests, TypeScript/build en browser-disabled-state geslaagd. Live provider-
acceptatie blijft open. Zie [research](research-executor.md) en
[browserbewijs](research-browser-evidence.md).

**12 september, autonomie:** bestaande nachtqueue/value engine/ochtendbrief hergebruikt.
Gaia toont begrensde status en ochtendbrief; vaste veilige bronscan werkt
handmatig en via optionele systemd-timer om 22:00. Scan doet geen provider- of
netwerkverzoek en maakt geen memory/task/cache-records. 305 backendtests plus
twee subtests, 35 webtests, TypeScript/build en browserherstel geslaagd. Live
externe researchacceptatie, muterende nachtacties en self-improvement blijven open. Zie
[autonomiebewijs](autonomy-browser-evidence.md).

**10 september:** Vandaag en Memory gebruiken echte lokale gegevens. Memory
ondersteunt zoeken, bronweergave, toevoegen, corrigeren en verwijderen met reden;
late zoekresultaten kunnen nieuwe verbinding niet overschrijven. 299 backendtests
plus twee subtests, 30 webtests, TypeScript/build en browseracceptatie zijn
geslaagd. Google Agenda/Gmail is gekozen als eerste alleen-lezen connector;
begrensde client, serverroutes en Gaia-UI zijn lokaal gereed; accountverbinding
en live acceptatie blijven open. Zie [acceptatiebewijs](memory-today-browser-evidence.md),
[Google alleen-lezen client](google-readonly.md) en
[Google-browseracceptatie](google-browser-evidence.md).

**9 september:** duurzame Chat, exacte context-/kostenapproval en Gaia-koppeling
zijn toegevoegd; oudere Werk-jobs zijn direct opvraagbaar. Zie [chat.md](chat.md)
en de actuele [handoff](handoff.md) voor verificatie. Installatie, echte Vandaag/
Memory-data, connectors, autonomie en doelhardware blijven afzonderlijke open
acceptatiestappen. Historische meetmomenten hieronder zijn geen actuele
volledigheidsclaim.

**Kostenherstel 8 september:** gevalideerde usage wordt vóór antwoordparsing duurzaam opgeslagen. Gaia-preview plus expliciete approval kan uitsluitend bewezen verbruik reconciliëren; geen antwoord-/taaksucces, geen herhaling en geen bewijsloze budgetvrijgave. 253 backendtests + twee subtests, 16 webtests/build en desktopbrowserproef geslaagd. Echte chat, oudere-jobdetailherstel en alle overige productcriteria blijven open.

**Nieuwste code 8 september:** Gaia-modelinvoer aangesloten: lokale tekst-/kostenpreview, afzonderlijke approval, invalidatie bij edits en herstel van onzekere verzending met dezelfde aanvraag-id. Leesbaar antwoord blijft na herladen beschikbaar. 238 backendtests + twee subtests, 14 webtests en desktopbrowserketen met nepmodel geslaagd. Geen live API-/hardwarebewijs; reconciliatie, echte chat en de oorspronkelijke volledige agentvisie blijven open. Zie [model-work.md](model-work.md).

**Nieuwste code 7 september:** stap 4 heeft nu echte Responses-transportcode en workerintegratie, standaard uit: tekst-/kostenapproval, gedeelde SQLite-reservering, usage-registratie en crashherstel zonder automatische betaalde herhaling. Gaia toont modeljobs met het juiste type/verbruik. Offline bewijs en open grenzen: [model-work.md](model-work.md). Nog geen live provider-/M40-test; Gaia-modelinvoer, reconciliatie en algemene agents blijven open. De oudere updates hieronder zijn historisch bewijs, geen actuele afronding van het volledige product.

**Update 7 september:** REC-01/02/05 bronherstel, aanvullende scan en integratie uitgevoerd; 185 backendtests plus zeven webbridge-tests geslaagd. Stap 2 is ook met echte HTTP/SQLite getest. Stappen 3 en 5 hebben nu één echte lokale verticale integratie: syntaxcontrole met duurzame checkpoints en Gaia-Werk, inclusief pauze/hervatten/annuleren en procescrashregressie. Dit is geen voltooiing van algemene agents. **Volgende code: echte begrensde modeluitvoering met kostenreservering en offline tests**, daarna chat en read-only connectors. Zie local-work.md; de oudere tabellen hieronder blijven de volledige featurecriteria bewaren.

Stand: 6 september 2026. De eigenaar vraagt volledige stapsgewijze uitvoering. **Prototype** is voorbeeldgedrag; **code aanwezig** is geen live integratie. Alleen passende controles rechtvaardigen “werkend”. Zie de [SSD-audit](server-recovery-audit.md) voor het actuele implementatiebewijs.

## Eerst continuïteit herstellen

| ID | Prioriteit | Status | Taak en acceptatiecriterium |
|---|---|---|---|
| REC-01 | P0 | Volledig lokaal hersteld | WSL read-only kopie inclusief .git en privéstate; archiefvergelijking, alle reguliere bestandshashes en git fsck geslaagd. Zie wsl-recovery.md. Volledige bronintegratie/publicatiescan volgt. |
| REC-02 | P0 | Aanvullende inventaris nodig | HEAD `6b1863b`, 16 lokale commits plus dirty werk behouden. Actuele grote server/store/testfiles nu beschikbaar; volledige tests kunnen na veilige integratie starten. |
| REC-03 | P0 | Uitgevoerd en build getest | Bestaande Gaia-frontend behouden in `apps/web`; SHA-256-kopiecontrole en build geslaagd; lint heeft nul errors en vijf bestaande warnings. |
| REC-04 | P0 | Vastgelegd in docs | Maak plan, backlog en Codex-hervatinstructies vindbaar. Verifieer na publicatie de GitHub-commit. |
| REC-05 | P0 | Selectie gecontroleerd | 73 bronbestanden geselecteerd, hashes vastgelegd; twee docs geschoond. Private logs/secrets/runtime uitgesloten. Herhaal bij aanvullende export. |

## Uitvoeringsvolgorde en voltooiingsvoorwaarden

1. **Herstelbasis:** actuele ontbrekende files terughalen, integriteit controleren, volledige bestaande tests uitvoeren. Geen vervangende stack of stilzwijgend terugzetten van oudere code.
2. **Eerlijk uitvoeringsbewijs:** lokale schijntestproducent gecorrigeerd op `codex/night-queue-evidence` (7 regressietests, 34 bestaande route-evals geslaagd). Niet-geïmplementeerde self-improvement blijft review/expliciete fout, nooit tests_passed of fictieve wijziging. Volledige store/HTTP-test en echte geïsoleerde patch/testuitvoerder blijven open; zie [bewijs](night-queue-evidence-repair.md).
3. **Duurzame werkcyclus:** één taak echt uitvoeren met opgeslagen events/checkpoints, herstart/retry/idempotentie en backendapproval voor concrete acties.
4. **Providers:** bestaande router/adapter uitbreiden met echte begrensde uitvoering. OpenAI optioneel en standaard uit totdat model, budget en datascopes gekozen zijn; offline tests vóór betaalde smoke-test. M40-route pas activeren na benchmark.
5. **Gaia verbinden:** bestaand ontwerp behouden; chat/werk/approval/memory koppelen aan werkelijke status. Fouten en mock/demo zichtbaar onderscheiden.
6. **Gecontroleerde autonomie:** nachtqueue, memory/value-engine, research en morning brief met budget, annulering en herstarttests; geen verzonnen resultaten.
7. **Connectors per stuk:** begin read-only; agenda/mail, serverbeheer, shopper, finance en printer vereisen eigen scopes, concrete approvals en regressietests. Externe pakketten pas na licentie-/onderhoud-/veiligheidscontrole.
8. **Ubuntu-oplevering:** reproduceerbare installatie, secretbeheer, healthchecks, private backup/restore, systemd, logrotatie en begrensde resources. Doelserver-preflight en delivery-smoke zijn bewezen op de gemeten M40/9.3-GB-VM; reboot/rollback, Podman-sandbox en fan-failsafe blijven aparte acceptatiechecks.

Releaseklaar betekent relevante acceptatiechecks aantoonbaar geslaagd, geen bekende kritieke veiligheidsfouten, begrensde kosten en herstelbare fouten. Een lokale mocktest bewijst geen werkende dienst of hardware.

## Functionaliteit, bewijs en volgende stap

| Onderdeel | Huidig bewijs | Volgende acceptatiecriterium |
|---|---|---|
| Vandaag / Chat / Werk / Memory | Frontendcode en ontwerp aanwezig | Bestaande vorm behouden; echte backendstatus koppelen zodra API bekend is |
| Langlopende agents | UI-prototype met doel, fases, ETA, team en checkpoints | Een echte taak overleeft workerherstart en browserherladen, hervat vanaf opgeslagen checkpoint en toont verifieerbaar resultaat |
| Voortgang en ETA | Vaste voorbeeldwaarden | Toon werkelijke events; onbekende ETA als onbekend, nooit schijnprecisie of timer als bewijs van werk |
| Automatische/handmatige agentkeuze | UI-prototype | Werkelijke router legt rolkeuze uit; scopes en toolrechten blijven server-side begrensd |
| Memory / routines | Visie en voorbeeldgraph | Duurzame opslag met bron, confidence, correctie en verwijdering; privacyregels toepassen |
| Self-learning | Visie en learning-preview | Gespreks-/foutsignaal produceert herleidbaar voorstel; verbetering wordt getest en is terugdraaibaar |
| Value Engine / toolbouwer | Scoremodel in conceptplan | Keuze uitvoeren, vragen, bewaren of afwijzen met reden, kosten en herbruikbaarheid; geen dubbel backlogitem |
| MCP/plugin discovery | Broncatalogus | Bestaande tools inventariseren; kandidaat beoordelen op onderhoud, permissies en compatibiliteit vóór installatie |
| Nachtcyclus | Gepland om 22:00 | Configureerbare tijdzone Europe/Amsterdam, budget, queue, onderbreken voor livegebruik en ochtendrapport |
| Lokale/externe modelrouter | Hardwarewens en kandidaten | M40-benchmark plus werkende fallback; geen onbewezen model/runtime als verplichte basis |
| Manager / Rabobank / marktdata | Visie | Eerst gecontroleerde read-only koppeling; externe geldacties vereisen specifieke backendapproval |
| Planner / Magister / mail / agenda | Visie, UI-agentrol | Eén echte bron aansluiten; concepten en wijzigingspreview met tijdzone en deduplicatie |
| Shopper / Marktplaats / Vinted / TicketSwap | Visie, UI-agentrol | Shortlist met bron/prijs/tijdstip; bericht, bod of aankoop afzonderlijk autoriseren |
| Server manager, beide servers | Visie, UI-agentrol | Read-only inventaris en periodiek rapport; concrete update-/herstartactie met bewijs en passende approval |
| 3D-referentiemaker | Gebruikerswens, nog geen bewezen pipeline | Zoek bronmodel of bruikbare aanzichten; lever referentiemodel met herkomst, schaal/onnauwkeurigheid en licentie |
| 3D-printermanager / camera / Fluidd | Gebruikerswens, UI-agentrol | Lees telemetrie/camera; meld concrete afwijking; instellingswijzigingen begrenzen en expliciet autoriseren |

De tabel bewaart de oorspronkelijke feature-acceptatiecriteria; de recente implementatie-inventaris staat in de audit. Decision Layer/modelrouter bestaan (34/34 evaluaties); agentrunner is mock, provideradapter dry-run, planner sampledata. Store-/HTTP-functionaliteit is beschreven maar door ontbrekende actuele files niet volledig verifieerbaar. Geen van deze onderdelen hoeft blind vanaf nul gebouwd te worden.

## Eerste verticale integratie na SSD-inventaris

1. Behoud de bestaande backendstack als die bruikbaar is; leg eventuele noodzakelijke afwijking met bewijs vast.
2. Koppel de bestaande Werk-UI aan één duurzame taak: aanmaken, echte stappen/events, pauze, hervatten en afgerond resultaat.
3. Test crash/herstart en dubbele verzoeken, inclusief een pending approval. Uitgevoerde externe acties mogen niet opnieuw worden uitgevoerd door een retry.
4. Sluit daarna één betrouwbare read-only tool aan en breid gericht uit met planner/memory/modelrouting.

## Concrete gebruikersscenario's

- **WK in de agenda:** bron en tijdzone verifiëren, preview tonen, gewenste agenda vaststellen, na autorisatie schrijven; opnieuw uitvoeren maakt geen duplicaten.
- **Reisresearch na vliegtickets/Airbnb-vraag:** optionele achtergrondtaak met budget en bestemming; resultaten, bronnen en datum bewaren; geen boeking uit een informatievraag afleiden.
- **Weer in Amsterdam bij een fout:** fout classificeren, begrensde retries en geschikte fallback; aantoonbaar antwoord leveren of concrete blokkade melden. Een structurele fout maakt een reparatietaak met regressiecontrole.

## Bronnen uit de oorspronkelijke ideeën

De GitHub-kandidaten staan in sectie 22 van het conceptplan. Hun eerdere onderhoudsbeoordelingen zijn niet allemaal opnieuw geverifieerd tijdens deze migratie. Onderstaande videobronnen zijn geregistreerd als inspiratie, nog niet inhoudelijk gecontroleerd:

- https://www.youtube.com/watch?v=AttKv_d7P04
- https://www.youtube.com/watch?v=cQqOkx5qnWo
- https://www.youtube.com/watch?v=19xCOJxWU0A

“Jcode” en “Ollm” moeten nog als exacte projecten worden geïdentificeerd. Colibri is de opgegeven repository `JustVugg/colibri`; de gewenste GLM-versie en compatibiliteit moeten nog worden bevestigd.
