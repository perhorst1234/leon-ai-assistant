# Werken aan Leon / Gaia

- Nieuwste modelwerk (8 september): Gaia-invoer met lokale kostenpreview, expliciete tekstapproval, aanvraag-id-herstel en leesbaar antwoord aangesloten. Browserketen met tijdelijke SQLite/nepmodel getest, inclusief gewijzigde tekst en herladen; geen betaalde calls. Zie `docs/model-work.md`. Volgende code: gecontroleerde reconciliatie en echte chat. `.env.example` is op verzoek lokaal van een sleutelachtige waarde ontdaan; overige gebruikerswijzigingen daarin blijven buiten de commit. `.env.local` privé laten. Nieuwe providercode niet testen met de echte sleutel zonder expliciete budgetkeuze.

- Nieuwste werk (7 september): bron geïntegreerd, 185 backendtests plus zeven webbridge-tests geslaagd; echte lokale worker en Gaia-Werk gekoppeld. Zie docs/local-work.md. Volgende code is begrensde modeluitvoering. De gebruiker vraagt minder procesadministratie en meer implementatie; houd handoff/checks kort.

- Lees `docs/handoff.md` en `docs/implementation-backlog.md` bij de start. Raadpleeg het conceptplan voor de productvisie en `apps/web/DESIGN.md` voor bestaande UI-keuzes.
- De gebruiker wil vanaf Windows en de Linux-server op hetzelfde werk kunnen voortbouwen. Houd code, afgerond werk, controles, open problemen en de concrete volgende stap bij in GitHub. Werk de handoff en backlog bij aan het einde van een betekenisvolle wijziging.
- Controleer branch, HEAD en onopgeslagen wijzigingen voordat je synchroniseert. Bewaar werk van de gebruiker; overschrijf geen SSD/serverkopie met deze repository.
- De SSD-code is volledig lokaal hersteld via WSL: zie `docs/wsl-recovery.md`. De oorspronkelijke gedeeltelijke snapshot staat op `codex/ssd-recovery-2026-09-06`; de volledige privébackup staat in `Documents/leon-ssd-full-2026-09-06`. Actuele server.py/store.py/test_control_plane.py en database zijn terug. Integreer gecontroleerde bron met `codex/night-queue-evidence`; publiceer geen privébackup. Bewaar Python/SQLite en ongecommitte serverwerk.
- Maak onderscheid tussen ontworpen, aanwezig in code, lokaal getest en getest op de doelserver. Een UI-demo is geen werkende agentruntime.
- Doelhardware: Ubuntu, Tesla M40, Xeon E5-2676 v3, 16 GB systeem-RAM als basis en mogelijk 32 GB. Phase 4 noemt 24 GB VRAM; nog meten. Controleer GPU-, driver-, CUDA- en modelcompatibiliteit. OpenAI is optioneel voor korte goedkope taken met expliciet budget, geen onbeperkte fallback.
- Houd lange taken hervatbaar met concrete checkpoints en bewijs. Leg testcommando's, uitkomsten en beperkingen vast; meld een mislukte push als niet gesynchroniseerd.
- Deze repository is openbaar. Commit geen `.env`, tokens, sleutels, persoonlijke logs, gesprekken, databasebestanden, schijfexports of modelgewichten. Controleer herstelde code vóór een push.
- Bestaande financiële, communicatie-, installatie- en serveracties in de productvisie hebben expliciete bevoegdheden nodig; UI-approval alleen is geen backendautorisatie.
