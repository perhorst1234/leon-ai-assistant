# Leon / Gaia — uitvoeringsbacklog

Stand: 6 september 2026. **Prototype** betekent bestaande frontendinteractie met voorbeelddata. **Te controleren** betekent dat werk op de SSD kan bestaan, maar nog niet is gelezen. Alleen een geslaagde passende controle rechtvaardigt “werkend”.

## Eerst continuïteit herstellen

| ID | Prioriteit | Status | Taak en acceptatiecriterium |
|---|---|---|---|
| REC-01 | P0 | Geblokkeerd op Windows-toegang | Vind `leon-ai-assistant` op de Crucial-SSD; maak een afzonderlijke leesbare kopie inclusief verborgen `.git`, zonder de bron te wijzigen. Noteer pad en kopiecontrole. |
| REC-02 | P0 | Wacht op REC-01 | Vergelijk SSD-HEAD, branches, remotes en dirty/untracked bestanden met GitHub. Inventariseer bestaande backend, configuratie, tests en laatste werkstatus. |
| REC-03 | P0 | Uitgevoerd en build getest | Bestaande Gaia-frontend behouden in `apps/web`; SHA-256-kopiecontrole en build geslaagd; lint heeft nul errors en vijf bestaande warnings. |
| REC-04 | P0 | Vastgelegd in docs | Maak plan, backlog en Codex-hervatinstructies vindbaar. Verifieer na publicatie de GitHub-commit. |
| REC-05 | P0 | Gepland | Controleer herstelde bestanden op secrets/persoonlijke data vóór toevoegen aan openbare GitHub. Scheid private runtimeback-up van codeback-up. |

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

Voor backendonderdelen is de SSD-implementatiestatus nog **te controleren**. Deze tabel is geen bewijs dat alles nog vanaf nul gebouwd moet worden.

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
