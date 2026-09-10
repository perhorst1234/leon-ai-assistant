# Google Agenda en Gmail — alleen-lezen client

Stand: 10 september 2026. Gebruiker koos Google Agenda/Gmail als eerste
connector. Client en geauthenticeerde serverroutes zijn aanwezig en offline
getest. Accountverbinding, Gaia-scherm en live Google-acceptatie zijn nog niet
uitgevoerd.

## Gedrag

- Standaard uit. Uitvoering vereist goedgekeurd connector-manifest, expliciet
  opgegeven configuratiesleutels, runtime credential-provider en passende OAuth-
  scope.
- Agenda gebruikt uitsluitend vaste Google Calendar-host en
  `calendar.events.readonly`. Tijdbereik, pagina's, items, antwoordgrootte en
  timeout zijn begrensd. Tijdzone en hele-dagafspraken worden behouden.
- Gmail gebruikt uitsluitend vaste Gmail-host en `gmail.metadata`.
  `messages.list` gebruikt geen `q`, omdat Google dat met deze scope niet
  toestaat. Detailverzoeken vragen alleen `From`, `Subject` en `Date`; inhoud,
  bijlagen en overige headers komen niet in resultaat.
- Optionele refresh-tokenwisseling gebruikt vaste Google OAuth-host, één poging
  en geen redirects. Credentials worden niet uit omgeving gelezen, opgeslagen
  of in resultaat/fouttekst geplaatst.
- Fouten zijn stabiele codes. Client doet geen automatische retries.
- `GET /api/google/status` toont alleen aan/uit, configuratiestatus en toegekende
  scope-status. Previewroutes voor agenda en mail vereisen expliciete bearer-
  autorisatie.
- Previewresultaten krijgen stabiele bronverwijzingen en worden niet automatisch
  in Leon opgeslagen. Toestemmingsaudit wordt vóór uitvoering vastgelegd;
  succes krijgt aanvullend uitvoeringsbewijs. Mislukking blijft zichtbaar zonder
  ten onrechte geslaagde uitvoering te claimen.

## Bewijs

- 26 gerichte client-/HTTP-routetests geslaagd.
- Onafhankelijke Python-reviews: geen resterende P1/P2-bevindingen.
- Volledige backendset na serverkoppeling: 299 tests plus twee subtests geslaagd.

## Nog nodig voor echte koppeling

1. Google Cloud OAuth-client en alleen-lezen toestemming door gebruiker.
2. Private credential-provider met veilige opslag en rotatie buiten repository.
3. Gaia-weergave plus browsertests voor status, agenda en mailmetadata.
4. Aparte bewuste importactie als gebruiker geselecteerde resultaten in Leon
   wil bewaren; preview zelf blijft zonder opslag.
5. Kleine live acceptatie tegen gekozen Google-account; geen mail- of
   kalenderwijzigingen.
