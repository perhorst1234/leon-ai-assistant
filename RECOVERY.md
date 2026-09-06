# Gedeeltelijke SSD-bronkopie

Ontwikkelbranch-notitie: `codex/night-queue-evidence` bevat een bewuste wijziging aan night_queue.py en nieuwe gerichte tests na de snapshot. Het manifest beschrijft uitsluitend de ongewijzigde herstelcommit 8ebd5a9 op `codex/ssd-recovery-2026-09-06`, niet de actuele ontwikkelinhoud. Zie docs/night-queue-evidence-repair.md en Git-diff voor de ontwikkeling.

Deze branch bewaart 73 geselecteerde bestanden uit de aangeleverde serverexport, inclusief ongecommitte werk. Het is geen startklare of volledig herstelde backend. Actuele server.py, store.py en test_control_plane.py ontbreken. Zie docs/server-recovery-audit.md en docs/server-recovery-manifest.json.

De bestaande Python/SQLite-stack is behouden. Alle broninhoud is identiek behalve twee gedocumenteerde hostnaamsanitisaties. Scriptmodi zijn hersteld naar 100755. docs/source-server-readme.md is historische serverdocumentatie: installatie-, URL- en runtimeclaims daarin zijn geen actuele verificatie of toestemming. Ook de seed bevat historische approvalstatus, geen nieuwe autorisatie.

Geen secrets, private logs of runtimebackup opgenomen. Main bevat de Gaia-frontend en actuele overdracht. Herstel eerst ontbrekende actuele files en test vóór integratie. Originele exportmappen blijven bewaard.
