# Werken aan Leon / Gaia

- 13 september, `codex/complete-leon`: geaccepteerde agentrun-review beweegt
  oudertaak atomisch via canonieke transities naar `review`, met begrensde
  runprovenance. Rejected/changes-requested laat taak staan; dubbele review is
  schrijfloos; `review → done` blijft expliciet. Evidenceprojectie max acht
  korte items; JSON boven 65.536 tekens wordt niet geparseerd. 332 backendtests
  plus twee subtests en Python-review zonder P1/P2. Zie
  `docs/agent-runtime-adapter-implementation.md`.

- 13 september, `codex/complete-leon`: geauthenticeerde read-only servermonitor
  en Gaia-kaart toegevoegd. Begrensde OS/uptime/load/memory/disk/procesmetadata,
  vaste schijflabels, connectoraudit en uit-schakelaar; geen commando's, logs,
  secrets of caller-paden. 328 backendtests + twee subtests, 42 webtests,
  TypeScript/build/lint en lokale browserproef geslaagd. Zie
  `docs/server-monitor.md` en `docs/server-monitor-browser-evidence.md`. Volgende:
  Ubuntu/M40-doelserveracceptatie of OS-sandbox voor echte patchtests.

- 13 september, `codex/complete-leon`: review-only self-improvement validator
  toegevoegd voor disposable Git-repositories. Exacte approvalbinding, eenmalig
  verbruik, pad-/secret-/Git-configblokkades en statische syntaxcontrole; gewijzigde
  code wordt nooit uitgevoerd. Zeven gerichte tests plus onafhankelijke review
  geslaagd. Zie `docs/self-improvement-sandbox.md`. Volgende stap: OS-sandbox en
  echte tests, of read-only servermonitor.

- 12 september, `codex/complete-leon`: Firecrawl v2 search-only Research-flow
  toegevoegd, standaard uit. Backend gebruikt vaste host, expliciete domeinen,
  caps, duurzame preview-ID/fingerprint, 15 minuten geldigheid en audit-outcomes;
  Gaia vereist preview vóór start. 314 backendtests + twee subtests, 39 webtests,
  TypeScript/build en browser-disabled-state geslaagd. Zie
  `docs/research-executor.md` en `docs/research-browser-evidence.md`. Volgende:
  kleine live provideracceptatie na key/budget, of doelserveracceptatie.

- 12 september, `codex/complete-leon`: Gaia toont begrensde autonomiestatus en
  ochtendbrief. Handmatige knop en optionele systemd-timer voeren uitsluitend
  veilige lokale bronindex uit; geen provider/netwerk of stille memory/task/cache-
  mutaties. Run blijft na herladen zichtbaar. 305 backendtests + twee subtests,
  35 webtests, TypeScript/build en browseracceptatie geslaagd. Zie
  `docs/autonomy-browser-evidence.md`. Volgende werk: echte read-only research-
  executor, daarna doelserveracceptatie.

- 10 september, `codex/complete-leon`: Vandaag en Memory gebruiken echte lokale
  gegevens; browserketen voor verbinden, bewaren, herladen, zoeken, corrigeren
  en verwijderen geslaagd. Google Agenda/Gmail alleen-lezen client is standaard
  uit; client, serverroutes en Gaia-preview zijn offline/browser-getest.
  Account-/live-integratie blijft open. 299 backendtests + twee subtests, 30
  webtests, TypeScript/build geslaagd. Zie `docs/memory-today-browser-evidence.md`,
  `docs/google-readonly.md` en `docs/google-browser-evidence.md`. Volgende werk:
  private Google OAuth credential-provider en kleine live read-only acceptatie.

- 9 september, `codex/complete-leon`: duurzame Chat + Gaia, goedkeuring bindt exacte context en beide kostengrenzen; replay/concurrency hersteld. Chatbrowserketen met nepmodel geslaagd. 269 backendtests + twee subtests, 19 webtests, typecheck/build geslaagd; npm audit nul kwetsbaarheden na gerichte updates. Installatie/backup/restore en configureerbare private DB toegevoegd; zie `docs/installation.md`, `docs/chat-browser-evidence.md`, `docs/web-validation.md` en nieuwste handoff. Volgende werk: echte Vandaag/Memory, read-only connector en Ubuntu/hardwareacceptatie. Gebruik lichte agents met smalle opdrachten; bewaak gedeeld limiet en reserveer ruimte voor verificatie/overdracht.

- Kostenherstel (8 september): gevalideerd verbruik wordt vóór antwoordparsing opgeslagen; Gaia kan een onzekere job met dat bewijs na expliciete approval kosten-only reconciliëren. Geen bewijs = geen vrijgave; geen betaalde retry of fictief antwoord. 253 backendtests + twee subtests, 16 webtests, build en desktopbrowserketen geslaagd. Zie docs/model-work.md. Volgende code: echte chat en detailherstel buiten de 100 nieuwste jobs. Geen live kosten of doelhardware getest.

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
