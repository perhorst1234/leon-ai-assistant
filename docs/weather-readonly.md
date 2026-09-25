# Weer in Amsterdam — live alleen-lezen connector

Stand: **25 september 2026**.

Gaia Vandaag toont actueel weer en een voorspelling voor drie dagen uit
Open-Meteo. De locatie staat server-side vast op Amsterdam
(`52.3676, 4.9041`, `Europe/Amsterdam`). De browser kan geen host, locatie,
queryvelden of periode aanleveren.

## Begrenzing

- alleen `GET /api/weather/current` achter de bestaande backendauthenticatie;
- alleen HTTPS naar `api.open-meteo.com/v1/forecast`;
- geen redirects, sleutel, account of schrijfactie;
- maximaal 64 KiB providerantwoord en tien seconden transporttimeout;
- exact huidige condities plus drie voorspeldagen;
- strikte type-, bereik-, datum-, tijdzone- en vormcontrole in backend en web;
- tien minuten geheugen-cache om providerverkeer te begrenzen;
- preflight, uitvoering en fouten komen in de connectoraudit.

De kaart vermeldt Open-Meteo en `CC BY 4.0` en linkt naar de
[Forecast API-documentatie](https://open-meteo.com/en/docs). Open-Meteo biedt
de no-key API voor niet-commercieel gebruik met fair-usegrenzen; er is geen
uptimegarantie. Zie de [pricingpagina](https://open-meteo.com/en/pricing) en
[voorwaarden](https://open-meteo.com/en/terms).

## Verificatie

Een echte providerproef op de doel-VM leverde Amsterdam, huidige condities en
drie voorspeldagen. De eerste call was een cache-miss, de tweede een cache-hit
en de audit-hashketen bleef geldig. Fouttests dekken een onjuiste methode,
ontbrekende auth, providerfout, te groot antwoord, ongeldige JSON, foutieve
typen/bereiken en misvormde frontenddata. De live proef schreef niets naar een
extern systeem en gebruikte geen account of sleutel.

Open grenzen: Open-Meteo is een modelverwachting en kan lokaal afwijken. De
cache is per backendproces en gaat verloren bij een herstart. Google en
Firecrawl blijven afzonderlijk uit totdat hun private credentials beschikbaar
zijn.
