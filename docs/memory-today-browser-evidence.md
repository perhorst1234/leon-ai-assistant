# Vandaag en Memory — lokaal acceptatiebewijs

Stand: 10 september 2026. Proef gebruikte tijdelijke SQLite-database,
synthetisch dashboardtoken en lokale backend/webserver. Geen provideraccount,
persoonlijke data of betaalde modelaanroep gebruikt.

## Bewezen

- `/api/overview` en `/api/memory` weigeren verzoeken zonder dashboardtoken en
  sturen geauthenticeerde antwoorden met `Cache-Control: no-store`.
- Vandaag toont werkelijke lege aantallen uit nieuwe database; geen verzonnen
  werk, weer, ETA of approvalstatus.
- Memory bewaart inhoud plus bron, overleeft herladen, zoekt via duurzame
  backend, corrigeert via gelabeld formulier en verwijdert pas met ingevulde
  reden. Verwijderde inhoud ontbreekt daarna in lijst en zoekresultaat.
- Verkeerd token kan zonder paginaherlading worden vervangen. Vertraagd oud
  zoekantwoord kan nieuwe verbinding of verversing niet overschrijven.
- Zoekexcerpt kan volledig opgeslagen geheugen niet overschrijven.
- Echte en ontwerpvoorbeeldmodus blijven zichtbaar gescheiden.
- Scherm op 1280×720 gecontroleerd: kop, lijst, invoer en detail zichtbaar;
  smalle schermen schakelen naar één kolom.

## Geautomatiseerde controle

- Backend: 288 tests plus twee subtests geslaagd.
- Web: 23 tests geslaagd.
- TypeScriptcontrole en productiebuild geslaagd.
- Lint: nul fouten; vijf bestaande ongebruikte-importwaarschuwingen in
  `page.tsx`.

## Open grens

Browserproef bewijst lokale productketen. Geen Ubuntu/M40-server, extern account
of live provider getest. Google Agenda/Gmail is gekozen als eerste alleen-lezen
koppeling; client, accountverbinding en live acceptatie blijven apart bewijs.
