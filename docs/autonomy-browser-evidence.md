# Veilige nachtvoorbereiding — acceptatiebewijs

Stand: 12 september 2026. Proef gebruikte tijdelijke SQLite en lokale
synthetische dashboardconfiguratie. Geen provider, internet, echt account,
persoonlijke data of betaalde modelaanroep is gebruikt.

## Werkende keten

1. Gaia Vandaag toont begrensde autonomiestatus uit `/api/overview`.
2. `Start veilige bronscan` verstuurt vaste economy-configuratie met alleen R1/R2
   en uitsluitend `index_new_sources`.
3. Backend indexeert lokale bronverwijzingen, bewaart run en genereert
   ochtendbrief met bronnen, aandacht, voorstellen en kostenraming.
4. UI toont één geslaagde actie, nul fouten, nul voorstellen en drie bronnen.
5. Pagina herladen wist dashboardtoken; na opnieuw verbinden verschijnen dezelfde
   opgeslagen run en ochtendbrief.
6. 1280x720-indeling blijft leesbaar en scrollbaar.

## Planning en grenzen

- `leon-autonomy.timer` plant dezelfde veilige bronscan dagelijks om 22:00 in
  `Europe/Amsterdam`; `Persistent=true` haalt gemiste run na downtime in.
- Timer wordt niet automatisch geïnstalleerd of aangezet.
- Scan maakt geen memory-items, taken of caches en doet geen provider- of
  netwerkverzoeken. Volledige muterende nachtqueue blijft handmatig/reviewwerk.
- Uitzonderingen tijdens ochtendbrief/finalisatie sluiten duurzame run als
  mislukt af. Geen verzonnen resultaat; databasefout blijft zichtbaar.

## Verificatie

- Volledige backend: 305 tests plus twee subtests geslaagd.
- Web: 35 tests, TypeScript en productiebouw geslaagd.
- Lint: nul fouten; vijf bestaande ongebruikte-importwaarschuwingen in
  `apps/web/app/page.tsx`.
- Onafhankelijke Python- en React-review: gemelde P1/P2-problemen gerepareerd.

## Nog open

Echte externe research-executor en gecontroleerde self-improvement bestaan nog
niet. Doelserver moet timer, tijdzone, herstart en resources live valideren.
