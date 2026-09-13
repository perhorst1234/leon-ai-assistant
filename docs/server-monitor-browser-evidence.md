# Servermonitor — browserbewijs

Datum: 13 september 2026. Omgeving: Gaia op `localhost:13000`, tijdelijke
`tests/ui_model_fixture.py` op `127.0.0.1:18765`, synthetisch dashboardtoken en
tijdelijke SQLite. Geen externe provider, echte sleutel of bestaande database.

Gecontroleerde keten:

1. Vandaag geopend en verbonden met fixturetoken.
2. Serverstatus verscheen naast Autonomie en Research.
3. Kaart toonde live load, totaal geheugen, uptime, Darwin/x86_64, drie vaste
   schijflabels en actief Leon-proces.
4. `Ververs` opnieuw gebruikt; load en vrije schijfruimte wijzigden, kaart bleef
   beschikbaar.
5. Weergave bevatte alleen `repository`, `state` en `database`; geen absoluut
   lokaal pad, PID, log, environmentwaarde of secret.
6. Darwin leverde geen standaardbibliotheekwaarde voor beschikbaar geheugen.
   Gaia toonde daarom `— / 32.0 GB`, gelijk aan API-status `partial`.

Automatische validatie bij dezelfde bronboom: 328 backendtests plus twee
subtests, 42 webtests, TypeScript zonder fouten, productiebuild geslaagd en lint
met nul fouten. Vijf bestaande ongebruikte-importwaarschuwingen in `page.tsx`
blijven buiten deze slice. Onafhankelijke React-review vond geen P1/P2.
