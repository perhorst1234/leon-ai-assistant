# Werken aan Leon / Gaia

- Lees `docs/handoff.md` en `docs/implementation-backlog.md` bij de start. Raadpleeg het conceptplan voor de productvisie en `apps/web/DESIGN.md` voor bestaande UI-keuzes.
- De gebruiker wil vanaf Windows en de Linux-server op hetzelfde werk kunnen voortbouwen. Houd code, afgerond werk, controles, open problemen en de concrete volgende stap bij in GitHub. Werk de handoff en backlog bij aan het einde van een betekenisvolle wijziging.
- Controleer branch, HEAD en onopgeslagen wijzigingen voordat je synchroniseert. Bewaar werk van de gebruiker; overschrijf geen SSD/serverkopie met deze repository.
- De SSD-code is nog niet geïnventariseerd. Kies geen vervangende backendstack en verklaar geen backendonderdeel ontbrekend op de server voordat die code is onderzocht.
- Maak onderscheid tussen ontworpen, aanwezig in code, lokaal getest en getest op de doelserver. Een UI-demo is geen werkende agentruntime.
- Doelhardware: Tesla M40 en Xeon E5-2676 v3. Controleer GPU-, driver-, CUDA- en modelcompatibiliteit; neem geen moderne GPU-features of specifieke VRAM-capaciteit aan.
- Houd lange taken hervatbaar met concrete checkpoints en bewijs. Leg testcommando's, uitkomsten en beperkingen vast; meld een mislukte push als niet gesynchroniseerd.
- Deze repository is openbaar. Commit geen `.env`, tokens, sleutels, persoonlijke logs, gesprekken, databasebestanden, schijfexports of modelgewichten. Controleer herstelde code vóór een push.
- Bestaande financiële, communicatie-, installatie- en serveracties in de productvisie hebben expliciete bevoegdheden nodig; UI-approval alleen is geen backendautorisatie.
