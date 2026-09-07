# Overdracht — Leon / Gaia

Stand: **7 september 2026**. De gebruiker wil vooral coderen; houd deze overdracht kort.

## Nieuwste werk

- Volledige SSD-bron hersteld; actuele server/store/tests geïntegreerd, inclusief ongecommitte serverwerk.
- Nachtqueue fabriceert geen succesvolle patches of testuitslagen meer, ook niet na R3-toestemming.
- Nieuwe echte lokale worker: `work_queue.py`, `local_worker.py`, `work_api.py`. SQLite-checkpoints, unieke request-id, lease/fencing, pauze/hervatten/annuleren, maximaal drie pogingen per onderbroken stap.
- Gaia-Werk gebruikt echte backendstatus. De oude demo blijft expliciet apart; geen fictieve ETA. Website en backend draaien lokaal op Node/Python; Cloudflare-demo is opt-in.
- Eerste actie is een echte read-only Python-syntaxcontrole met bronhashes. **Nog geen LLM-agent, betaalde call of autonome codewijziging.**
- Bestaande hervatwatch gerepareerd: wacht op beide uitvoercollectoren vóór classificatie; stdout/stderr blijven gescheiden.

## Verificatie

Zie [uitvoering en testbewijs](local-work.md). Browserketen getest met tijdelijke SQLite en nepcredential: taak maken → wachtrij → pauze → hervat → 1/3 checkpoint → pagina herladen → hetzelfde checkpoint → afzonderlijke workerprocessen → afgerond 3/3. Geen private recoverydatabase gebruikt.

## Volgende codewerk

1. Echte begrensde modeluitvoering aan de bestaande router koppelen, standaard uit; eerst offline transporttests, kostenreservering en afhandeling van een onzekere API-uitkomst.
2. De worker uitbreiden met die concrete actie; side-effecting tools vereisen een afzonderlijk approval-/idempotentiecontract. Het huidige herstel mag read-only werk herhalen, niet willekeurig betalingen/berichten herhalen.
3. Echte chat/resultaten in Gaia koppelen; daarna één read-only connector. Bewaar het bestaande ontwerp.
4. Ubuntu-installatie/systemd, private backup/restore en doelhardware meten zodra de server beschikbaar is.

Store (~8.400 regels), server (~4.450) en oorspronkelijke tests (~5.150) blijven groot. Nieuwe verantwoordelijkheden in eigen modules houden, server alleen koppelen; geen brede refactor zonder relevante tests.

## Bron, privacy en synchronisatie

Werkkloon: `C:/Users/perhorst/Documents/ChatGPT/New project/leon-ai-assistant`.
Volledige ongewijzigde private recovery: `C:/Users/perhorst/Documents/leon-ssd-full-2026-09-06`.
Server-HEAD: `6b1863b6e1fdc612672c816ac048313c677115ca`, 16 lokale commits plus dirty werk. Alle reguliere kopiehashes en Git-objecten gecontroleerd. Archief bevat credentials; nooit publiceren. Database is gekopieerd, geen live restore geclaimd.

`codex/ssd-recovery-2026-09-06` blijft de historische gedeeltelijke snapshot. De ontwikkelbranch `codex/night-queue-evidence` verenigt die bron met de actuele main-overdracht. Originele servergeschiedenis/private logs worden niet gepusht. Zie [WSL-bewijs](wsl-recovery.md) en [historische audit](server-recovery-audit.md).

Doel blijft Ubuntu, M40, Xeon E5-2676 v3, 16 GB RAM (32 optioneel). Nog open: GPU/driver/modelmeting, live providers, financiële/communicatie/installer-approvalketens, connectors, volledige productacceptatie. Phase-4-stories zijn niet afgevinkt op basis van mocktests.

Voor hervatten op de server: controleer HEAD/branch/dirty werk en gebruik bij twijfel een nieuwe kloon; overschrijf de oorspronkelijke bron of database niet. GitHub is de code-/planoverdracht, geen backup van lopende processen of gesprekken.
