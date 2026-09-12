# Research — browseracceptatie

Datum: 12 september 2026. Omgeving: Gaia op `localhost:13000`, tijdelijke
Leon-fixture op `127.0.0.1:18765`, geen externe provider en geen echte sleutel.

Gecontroleerd:

- verbinden met tijdelijk dashboardtoken toont nieuwe read-only Research-kaart;
- query plus expliciete domeinallowlist levert controleerbare preview;
- uitgeschakelde server toont `disabled`, Firecrawl, risico R1 en concrete uitleg;
- startknop blijft uit wanneer backend `execution_allowed=false` teruggeeft;
- wijziging van query wist oude preview en houdt start geblokkeerd;
- token blijft alleen in geheugen van Gaia-weergave.

Volledige live search is niet geclaimd. Die vereist
`RESEARCH_EXECUTOR_ENABLED=true`, `FIRECRAWL_API_KEY`, kleine
`RESEARCH_ALLOWED_DOMAINS`-lijst en gekozen providerbudget. Offline provider-
en HTTP-tests bewijzen contract, caps, server-side previewbinding, auth,
resultaatfiltering en auditgedrag zonder betaalde call.
