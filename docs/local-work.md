# Echte lokale uitvoering — 7 september 2026

## Gebouwd

- Bestaande Python/SQLite-backend volledig aangevuld uit de actuele SSD-werkmap. Geen oudere reconstructie.
- `WorkQueue` koppelt uitvoeringen aan bestaande taken; transactionele checkpoints en audit, UUID-deduplicatie, lease van 30 seconden met fencing, maximaal drie pogingen per stap, pauze/hervatten/annuleren. Een succesvolle check voltooit de bovenliggende taak niet.
- `LocalWorker` voert echt een vaste Python-syntaxcontrole uit: bronhashes → AST-controle → bronversie opnieuw bevestigen. Maximaal 256 Python-files, 1 MiB per file en 8 MiB totaal. Geen imports/uitvoering van geïnspecteerde code, shell, providers of bronwijzigingen. Een bronwijziging tussen checkpoints laat de taak falen.
- `/api/work/jobs`, `/api/work/control`, `/api/work/tasks` en Gaia-Werk zijn gekoppeld. Dashboardtoken vereist op de webbridge; geen open proxy, geen cross-origin writes en geen token in clientbundles. Token alleen in componentgeheugen; opnieuw verbinden na herladen.
- Hervatwatch wacht op de stdout/stderr-collectoren voordat rate-limit-output wordt geïnterpreteerd. Een vertraagde-tee-regressie reproduceerde eerst de fout en slaagt na de reparatie.

## Starten op dezelfde lokale machine

Backend: stel een sterk privé-`LEON_DASHBOARD_TOKEN` en `LEON_DASHBOARD_AUTH_MODE=required` in de procesomgeving in. Vanuit de repository:

```bash
PYTHONPATH=src python3 -m leon_control_plane.server
```

Worker in een tweede terminal, dezelfde repository/database:

```bash
PYTHONPATH=src python3 -m leon_control_plane.local_worker
```

`--once` verwerkt maximaal één checkpoint. De worker kan een interrupted read herhalen; deze garantie mag niet voor betalingen of andere side effects worden hergebruikt.

Webserver: zet hetzelfde dashboardtoken in `LEON_DASHBOARD_TOKEN` en `LEON_BACKEND_URL=http://127.0.0.1:8765`, nooit een `NEXT_PUBLIC_` secret. Vanuit `apps/web`: `npm ci`, `npm run dev -- --host 127.0.0.1`. Voor een build: `npm run build`, daarna `npm start`. Deze configuratie gebruikt standaard Node voor Ubuntu; de oorspronkelijke Cloudflare-demo is alleen actief bij `LEON_CLOUDFLARE_PREVIEW=1`. Zie [Vinext-runtimeinformatie](https://github.com/cloudflare/vinext#deployment).

Open Werk → Echte taken → verbind met het dashboardtoken → maak of kies een controletaak → Start echte controle. De worker moet apart draaien. Overige ruimtes blijven demo; er is nog geen live AI-chat. De publieke bestaande website is niet opnieuw gedeployd.

## Gemeten bewijs

- Ubuntu 26.04/WSL, Python 3.14.4, pytest 9.0.2: **185 passed, 2 subtests passed in 19.73s**, exit 0, ook na het vervangen van vaste nepcredentials door proceslokale fixtures. Volledige oorspronkelijke suite plus scheduler-, worker- en watchregressies. Onderstaande opdracht blokkeert externe netwerktoegang en laat alleen loopback toe; uitvoeren met geschikte lokale rechten:

```bash
unshare --net --fork sh -c 'ip link set lo up; PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider --tb=short'
```

- Node 24: zeven bridge-tests geslaagd (`cd apps/web && npm test`), TypeScript-check geslaagd, lint nul errors/vijf bestaande warnings, lokale Node-mode build geslaagd. Geen nieuwe dependency nodig.
- Echte browser → Node-bridge → Python → tijdelijke SQLite → afzonderlijke workerprocessen: pauze blokkeert uitvoering, hervatten maakt 1/3 checkpoint, pagina herladen behoudt 1/3, twee nieuwe workerprocessen leveren 3/3 op. HTTP-uitval toont onbekende status, geen aangenomen succes. Slechts synthetisch dashboardtoken en aparte tijdelijke state gebruikt.
- Productie-startsmoke vanuit de tool werd geblokkeerd; geen productieproces of deployment geclaimd. Ontwikkelruntime en build zijn wel getest. Doel-M40/server, mobiele lay-out, echte modelcalls en volledige externe approvalketens blijven te verifiëren.
- Vertrouwen B voor deze beperkte lokale verticale integratie; het volledige product blijft onaf. Nieuwe queue/worker/API hebben eigen kleine modules; de bestaande store is byte-identiek, server heeft alleen 12 regels koppeling erbij. Geen tweede taakmanager of nieuwe backendstack.

## Herkomst aanvullende bron

Volledige private recovery blijft ongewijzigd; archief/hashcontrole in [wsl-recovery.md](wsl-recovery.md). De 73 bronhashes van de oorspronkelijke selectie komen overeen met de volledige SSD-kopie. Het oorspronkelijke plan heeft Git-blob `957a27ea4cec1782bf46871d734e6babcb5bc521` en is identiek aan de oude planbasis; secties 1–24 zijn behouden.

| Hersteld bestand | Originele SHA-256 | Publicatiewijziging |
|---|---|---|
| server.py | ad7048dbc83f612b681a9b4daaa2ce8270fb3e0dba8d327ee3b5682c31b5671c | Alleen work-API-import en routing |
| store.py | b3e9524bcfb1d4fabb64b9201d777c426cefd28aa0b777fff055f5f2a6bf519e | Geen |
| test_control_plane.py | 04b44ddf8ec1d0d9b8c6944792aed484d4efc6c1929eff9bc8f6027532602f44 | Zes private-hostnamefixtures geschoond; oude fictieve self-improvementverwachting vervangen; HTTP-regressie erbij; vaste nepcredentials vervangen door synthetische proceslokale fixtures |

Gerichte credentialscan: nieuw gepubliceerde matches zijn expliciete synthetische testfixtures; geen echte sleutels of private runtime meegenomen. Dit is geen volledige security-audit. Het oude `server-recovery-manifest.json` beschrijft bewust de historische gedeeltelijke snapshot.
