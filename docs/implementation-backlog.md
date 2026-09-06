# Leon / Gaia — uitvoeringsbacklog

Stand: 6 september 2026. De eigenaar vraagt volledige stapsgewijze uitvoering. **Prototype** is voorbeeldgedrag; **code aanwezig** is geen live integratie. Alleen passende controles rechtvaardigen “werkend”. Zie de [SSD-audit](server-recovery-audit.md) voor het actuele implementatiebewijs.

## Eerst continuïteit herstellen

| ID | Prioriteit | Status | Taak en acceptatiecriterium |
|---|---|---|---|
| REC-01 | P0 | Gedeeltelijk hersteld | Export ontvangen; drie centrale bron/testfiles en een Git-object ontbreken. Nieuwe volledige export vergelijken zonder de bron te wijzigen. |
| REC-02 | P0 | Inventaris uitgevoerd | HEAD `6b1863b`, 16 lokale commits plus dirty werk; Python-stack en mock/dry-rungrenzen onderzocht. Volledige tests wachten op REC-01. |
| REC-03 | P0 | Uitgevoerd en build getest | Bestaande Gaia-frontend behouden in `apps/web`; SHA-256-kopiecontrole en build geslaagd; lint heeft nul errors en vijf bestaande warnings. |
| REC-04 | P0 | Vastgelegd in docs | Maak plan, backlog en Codex-hervatinstructies vindbaar. Verifieer na publicatie de GitHub-commit. |
| REC-05 | P0 | Selectie gecontroleerd | 73 bronbestanden geselecteerd, hashes vastgelegd; twee docs geschoond. Private logs/secrets/runtime uitgesloten. Herhaal bij aanvullende export. |

## Uitvoeringsvolgorde en voltooiingsvoorwaarden

1. **Herstelbasis:** actuele ontbrekende files terughalen, integriteit controleren, volledige bestaande tests uitvoeren. Geen vervangende stack of stilzwijgend terugzetten van oudere code.
2. **Eerlijk uitvoeringsbewijs:** P1 in night_queue corrigeren: geen tests_passed zonder werkelijk testresultaat. Regressietests voor dry-run, gefaalde en niet uitgevoerde tests.
3. **Duurzame werkcyclus:** één taak echt uitvoeren met opgeslagen events/checkpoints, herstart/retry/idempotentie en backendapproval voor concrete acties.
4. **Providers:** bestaande router/adapter uitbreiden met echte begrensde uitvoering. OpenAI optioneel en standaard uit totdat model, budget en datascopes gekozen zijn; offline tests vóór betaalde smoke-test. M40-route pas activeren na benchmark.
5. **Gaia verbinden:** bestaand ontwerp behouden; chat/werk/approval/memory koppelen aan werkelijke status. Fouten en mock/demo zichtbaar onderscheiden.
6. **Gecontroleerde autonomie:** nachtqueue, memory/value-engine, research en morning brief met budget, annulering en herstarttests; geen verzonnen resultaten.
7. **Connectors per stuk:** begin read-only; agenda/mail, serverbeheer, shopper, finance en printer vereisen eigen scopes, concrete approvals en regressietests. Externe pakketten pas na licentie-/onderhoud-/veiligheidscontrole.
8. **Ubuntu-oplevering:** reproduceerbare installatie, secretbeheer, healthchecks, private backup/restore, systemd, logrotatie en begrensde resources. Test op 16 GB RAM/M40; 32 GB blijft optioneel. Fan-control pas na sensoren en fail-safe test.

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
