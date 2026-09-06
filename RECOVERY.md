# Gedeeltelijke SSD-bronkopie

Deze branch bewaart 73 geselecteerde bestanden uit de aangeleverde serverexport, inclusief ongecommitte werk. Het is geen startklare of volledig herstelde backend. Actuele server.py, store.py en test_control_plane.py ontbreken. Zie docs/server-recovery-audit.md en docs/server-recovery-manifest.json.

De bestaande Python/SQLite-stack is behouden. Alle broninhoud is identiek behalve twee gedocumenteerde hostnaamsanitisaties. Scriptmodi zijn hersteld naar 100755. docs/source-server-readme.md is historische serverdocumentatie: installatie-, URL- en runtimeclaims daarin zijn geen actuele verificatie of toestemming. Ook de seed bevat historische approvalstatus, geen nieuwe autorisatie.

Geen secrets, private logs of runtimebackup opgenomen. Main bevat de Gaia-frontend en actuele overdracht. Herstel eerst ontbrekende actuele files en test vóór integratie. Originele exportmappen blijven bewaard.
