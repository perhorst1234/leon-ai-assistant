# Checkpoint

Nieuwste werk: oorspronkelijke suite nu 158 tests + twee subtests geslaagd in Ubuntu/WSL, tijdelijke SQLite/HTTP, geen externe netwerktoegang. Op verzoek minder administratie en direct backlogstap 3 coderen.

Uitvoeringsslice: echte read-only projectcontrole, gekoppeld aan bestaande task-id, met SQLite-checkpoints, lease/fencing, idempotente aanmaak, pauze/hervatten/annuleren en begrensd herstel na crash. Geen generieke shell, externe calls, kosten of zelfwijziging. Een geslaagde controle voltooit niet automatisch de bovenliggende producttaak.
Change Necessity: code-change; mock/config alleen voert geen controle uit en herstart geen worker. Minimaal drie kleine eigenaren voor queue, vaste lokale actie/worker en HTTP-koppeling; bestaande store ongewijzigd, server wiring-only. TDD off/skipped; regressies voor echte resultaten, herstart, concurrency, stale worker, annulering en HTTP verplicht.
Complexiteit: nieuwe queue/worker elk onder 400 regels; geen nieuwe verantwoordelijkheid in de grote store/server. Behoud mockendpoint expliciet tot echte providerroute bestaat. Taakstart behoudt bestaande herstel/mergewijzigingen op codex/night-queue-evidence, HEAD 8f3adfb, MERGE_HEAD 9e7c0ab, één werkboom; alleen eigen nieuwe wijzigingen toevoegen.

Actief: REC-01 volledige export verkrijgen. REC-05 openbare gedeeltelijke bronback-up gepubliceerd en teruggelezen: herstelcommit 8ebd5a913d91c9c99ccdf82cce00f2df86db66e9, 73 hashes en bestandsmodi gecontroleerd.

Gedaan: inventaris, 22 syntaxchecks, 34/34 route-evals; frontend eerder gebouwd. Huidige vraag voegt Ubuntu, 16/32 GB RAM en optionele goedkope OpenAI-route toe.

Volgende stap: GitHub-publicatie verifiëren; ontbrekende actuele server.py/store.py/test_control_plane.py en Git-object van gebruiker verkrijgen. Daarna volledige tests en P1 schijntestresultaten corrigeren. Zie handoff en backlog voor vervolgbatches.

Drift: binnen gebruikersvisie en bestaande Python-stack. Geen volledige releaseclaim; geen runtime- of privacyscope uitgebreid. Snapshotbranch behouden totdat volledige bron veilig samengevoegd kan worden. Ontbrekende files zijn een herstelblokkade, geen reden nieuwe backend te verzinnen.

Resume: lees audit, handoff, actuele Git-status en manifeste hashes voordat implementatie verdergaat. Productdoel blijft actief.

Nieuwste slice: volledige WSL-recovery is geverifieerd (zie wsl-recovery.md). Integreer server/store/testbron op codex/night-queue-evidence; behoud de zeven bewezen veiligheidsregressies, voer volledige tests in Ubuntu uit en publiceer uitsluitend gescande bron.

TaskStartSnapshot: main 9e7c0ab schoon, één werkboom, ontwikkelbranch 8f3adfb schoon. Main wordt geïntegreerd; alleen eigen documentatieconflicten, nieuwste main-context behouden. Source Necessity: bronherstel/code-change, geen vervangende stack. TDD off/skipped voor import; oorspronkelijke tests en gerichte regressies wel uitvoeren. Architectuurreview: geen nieuwe architectuur bij kopie; nader beoordelen bij echte reparatie. Bestaande server/store/test zijn groot: niet uitbreiden met nieuwe verantwoordelijkheden in deze slice.
