# Google Agenda en Gmail — alleen-lezen client

Stand: 10 september 2026. Gebruiker koos Google Agenda/Gmail als eerste
connector. Clientcode is aanwezig en offline getest. Accountverbinding,
serverroute, Gaia-scherm en live Google-acceptatie zijn nog niet uitgevoerd.

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

## Bewijs

- 15 gerichte clienttests geslaagd.
- 18 connectorgerichte tests geslaagd.
- Onafhankelijke Python-review: geen resterende P1/P2-bevindingen.
- Volledige backendset na toevoeging: 288 tests plus twee subtests geslaagd.

## Nog nodig voor echte koppeling

1. Google Cloud OAuth-client en alleen-lezen toestemming door gebruiker.
2. Private credential-provider met veilige opslag en rotatie buiten repository.
3. Backendroutes die toestemming registreren, client aanroepen en genormaliseerde
   bronrecords via bestaande Leon-store bewaren.
4. Gaia-weergave plus offline HTTP/browsertests.
5. Kleine live acceptatie tegen gekozen Google-account; geen mail- of
   kalenderwijzigingen.
