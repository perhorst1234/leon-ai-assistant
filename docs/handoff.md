# Overdracht — Leon / Gaia

Stand: **13 september 2026**. De gebruiker wil vooral coderen; houd deze overdracht kort.

## Lopende aanvulling

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

Doel blijft Ubuntu, M40, Xeon E5-2676 v3, 16 GB RAM (32 optioneel). Nog open: GPU/driver/modelmeting, live providers, financiële/communicatie/installer-approvalketens, connectors, volledige productacceptatie. Phase-4-stories zijn niet afgevinkt op basis van mocktests.

Voor hervatten op de server: controleer HEAD/branch/dirty werk en gebruik bij twijfel een nieuwe kloon; overschrijf de oorspronkelijke bron of database niet. GitHub is de code-/planoverdracht, geen backup van lopende processen of gesprekken.
