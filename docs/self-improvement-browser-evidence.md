# Gaia self-improvement browserbewijs

Stand: 13 september 2026. Testomgeving gebruikte tijdelijke SQLite, lokale
Leon-backend en Gaia-devserver. Geen provider, extern netwerk, private database
of productiebron werd gewijzigd.

Geteste keten:

1. Werk openen en met synthetisch dashboardtoken verbinden.
2. Ingeklapte **Geavanceerde codecontrole** openen.
3. Geldige begrensde README-patch en bestaande file-allowlist invoeren.
4. Preview maken; Gaia toont exact bestand, `git_diff_check`, patchvingerafdruk,
   review-only grens en uitgeschakelde uitvoerknop.
5. Checkbox aanvinken en daarna invoer wijzigen; preview en approval verdwijnen.
6. Preview opnieuw maken, exacte checkbox aanvinken en review uitvoeren.
7. Zichtbare uitkomst: statische validatie geslaagd, tijdelijke map opgeruimd,
   menselijke review vereist en broncode niet toegepast of uitgevoerd.

Backendlogs bevestigden `preview` HTTP 201, scoped `approve` HTTP 200 en `run`
HTTP 200. README bleef inhoudelijk ongewijzigd en tijdelijke requestmappen waren
na afloop afwezig. Browser stuurde patch niet automatisch opnieuw.

Aanvullend bewijs: 345 backendtests plus twee subtests, 46 webtests, TypeScript,
productiebouw en lint zonder fouten. Vijf bestaande ongebruikte-importwarnings in
`app/page.tsx` blijven buiten deze wijziging. Onafhankelijke Python-, security-
en React-review vonden na racefix geen P1/P2.
