# Overdracht — Leon AI Assistant / Gaia

Stand: **6 september 2026**. De eigenaar vraagt het bestaande project stap voor stap af te maken. Doel: Ubuntu, Tesla M40, Xeon E5-2676 v3, 16 GB RAM (32 GB optioneel). OpenAI mag korte goedkope taken ondersteunen na budget- en privacyconfiguratie; sleutel blijft buiten GitHub.

## Actieve checkpoint

- Gedaan: Gaia-frontend behouden op main (importcommit `ed6dfb2`), SSD-export onderzocht, 22 aanwezige Python-modules syntax-getest, 34/34 routeringsevaluaties geslaagd.
- Actieve stap: gecontroleerde gedeeltelijke snapshot bewaren op `codex/ssd-recovery-2026-09-06` en export compleet krijgen.
- Vervolgwerk op `codex/night-queue-evidence`: scheduler fabriceert geen succesvolle patch/testresultaten meer; zeven gerichte regressietests en 34 routeringsevaluaties geslaagd. De actuele werkkloon staat op deze ontwikkelbranch. Herstelbranch blijft de oorspronkelijke snapshot. Zie [reparatiebewijs](night-queue-evidence-repair.md).
- Blokkade voor backendstart: actuele `src/leon_control_plane/server.py`, `src/leon_control_plane/store.py` en `tests/test_control_plane.py` ontbreken. Ook de Git-blob van store.py op server-HEAD ontbreekt.
- Daarna: volledige bestaande tests, onterecht geslaagde nachtelijke self-improvement-tests corrigeren, één echte hervatbare taak en Gaia-Werk-UI koppelen.
- Update volgende stap: lokale schijntestproducent is gecorrigeerd; na volledige export ook store/HTTP en oorspronkelijke tests controleren, vervolgens echte patch-/testuitvoering en hervatbare taken bouwen.
- Niet geclaimd: volledige recovery, live providers, gevalideerde approvalketen, externe connectors of geteste Ubuntu/M40-runtime.

Zie [audit](server-recovery-audit.md), [backlog](implementation-backlog.md) en [hardware](hardware.md).

## Bronnen

De aangeleverde Windows-bronnen zijn `C:/Users/perhorst/Documents/leon-ai-assistant` en `C:/Users/perhorst/Documents/leon-workspace`. Deze mappen blijven ongewijzigd. GitHub-werkkloon: `C:/Users/perhorst/Documents/ChatGPT/New project/leon-ai-assistant`. Afzonderlijke geschoonde snapshot: `leon-server-recovery` naast die kloon.

Server-HEAD: `6b1863b6e1fdc612672c816ac048313c677115ca`, met 16 lokale commits na `d0f7ba0` plus ongecommitte wijzigingen. De oude geschiedenis bevat private logs en een ontbrekend object; GitHub krijgt daarom een gecontroleerde bron-snapshot. De herstelbranch bevat een manifest met hashes en commitnamen. Phase 4 heeft tien stories, alle `passes=false`. Bewaar de bestaande Python/SQLite-stack.

`leon-workspace` bevat ondersteunend research-/agentmateriaal, geen alternatieve backend. Private outputs blijven lokaal. Er is geen SQLite-runtimebackup aangetroffen: bestaande memories, taken en auditgeschiedenis zijn niet veiliggesteld door deze GitHub-publicatie.

## Eerstvolgende actie

Maak een nieuwe volledige export van de drie ontbrekende bron/testfiles, `docs/personal-ai-assistant-plan.md` en verborgen `.git`. Bewaar originele SSD en eerdere export. Controleer `git fsck --full --no-reflogs --no-dangling` opnieuw. Oudere store.py-versies zijn geen vervanging voor de actuele werkmapversie zonder expliciete reconstructiekeuze.

Crucial CT525MX300SSD1: 525.110.100.480 bytes. Schijfnummers veranderen. DiskGenius was verhoogd en niet vanuit Codex bedienbaar; WSL was afwezig. Geen format-, repair- of partitioneringsactie uitvoeren. Oorzaak van onvolledige export is nog onbekend.

Na herstel: vergelijk verschillen en voer tests met tijdelijke state uit. Geen oude seed-approval als nieuwe toestemming gebruiken.

## Bewijs en beperkingen

- Python 3.14: `ast.parse` op 22 aanwezige modules geslaagd, zonder bytecodewrites.
- `evaluate_cases(load_eval_cases(), release_label="ssd-export-audit-2026-09-06")` rechtstreeks uit decision_layer: 34/34, 15 gate-cases, nul gerapporteerde safety failures. Geen API-calls of databasewrites.
- Volledige HTTP/store-tests en serverstartup niet uitgevoerd: actuele files ontbreken.
- Eerdere frontendcontrole: 15 importfiles hash-vergeleken; npm ci, lint en build geslaagd (Node 24.14.1/npm 11.11.0), vijf bestaande lintwarnings. Geen nieuwe deployment/browsertest.
- Bronselectie hash-gecontroleerd; privétailnethostnaam in twee docs vervangen. Gerichte credentialscan is geen volledige security-audit.
- Plansecties 1–24 blijven productcontext, sectie 0 bevat actuele status.

## Hervatten op server of andere computer

Inspecteer bestaande map, branch, HEAD en dirty werk vóór synchronisatie. Kloon zo nodig in een nieuwe map en lees deze handoff, audit en backlog; neem herstelbranch expliciet mee. GitHub is geen private databasebackup of draaiende worker.

Per stap: acceptatiecriterium, minimale wijziging, passende tests, documentatie en commit samen synchroniseren, remote teruglezen. Nooit een niet-uitgevoerde test groen boeken. Het ingestelde productdoel is nog actief; hardwaretests en echte integraties vereisen later de server, budget/scopes en diensttoegang.
