# Overdracht — Leon / Gaia

Stand: **8 september 2026**. De gebruiker wil vooral coderen; houd deze overdracht kort.

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

1. Vandaag en Memory op echte gegevens aansluiten; daarna één read-only connector. Chat en detailherstel buiten de 100 nieuwste jobs zijn inmiddels toegevoegd. Bewaar het bestaande ontwerp. Side-effecting tools hebben een eigen backendapproval-/idempotentiecontract nodig.
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
