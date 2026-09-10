# Google alleen-lezen — browseracceptatie

Stand: 10 september 2026. Proef draaide tegen tijdelijke SQLite, een synthetische
Google-client en een niet-geheime lokale dashboardtoken. Geen Google-account,
OAuth-secret, echte mail, echte agenda of extern netwerkverzoek is gebruikt.

## Gecontroleerde keten

1. Gaia Vandaag verbond met de lokale backend en haalde Google-status op.
2. Scherm toonde `Geconfigureerd`, beide toegekende read-only scopes en meldde
   dat previewdata niet wordt opgeslagen.
3. Agenda bleef leeg tot expliciete klik. Daarna verschenen een tijdafspraak en
   een hele-dagafspraak met `google:calendar:event:*` als bronverwijzing.
4. Gmail bleef leeg tot aparte expliciete klik. Daarna verschenen uitsluitend
   afzender, onderwerp, datum en `google:gmail:message:*`; geen inhoud of bijlage.
5. Herladen verwijderde dashboardtoken en previewresultaten uit de weergave.
6. 1280x720-weergave bleef bedienbaar; Gaia-avatar bedekt echte Vandaag-data
   niet. Ontwerpvoorbeeld en andere ruimtes behouden de avatar.

## Regressiebewijs

- 30 webtests geslaagd, inclusief vaste proxyroutes/methoden, strikte
  responsnormalisatie, limiet 10 en maximaal zeven lokale Amsterdam-dagen.
- Zomertijd-einde: precies zeven lokale dagen is geldig ondanks 169 verstreken
  UTC-uren; zeven dagen plus één minuut wordt geweigerd.
- Hele-dagdatums verschuiven niet door browsertijdzone.
- TypeScript geslaagd; lint nul fouten en vijf al bestaande waarschuwingen in
  `app/page.tsx`; productiebouw geslaagd.
- React-review vond na reparatie geen kritieke of hoge bevindingen. Beide P2-
  tijdzonebevindingen zijn opgelost en met regressietests vastgelegd.

## Open grens

Echte accountacceptatie blijft nodig: OAuth-client aanmaken, minimale scopes
toestaan via een private credential-provider en één kleine read-only proef doen.
Preview schrijft niets naar Leon; bewaren vereist later een aparte bewuste
importactie.
