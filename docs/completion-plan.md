# Leon afronden — bijgewerkt 25 september 2026

Doel: de bestaande productvisie afmaken met aantoonbare werking. Geen demo,
mocktest of onbereikbare hardware als afgeronde integratie tellen.

## Werkbasis

- Actuele GitHub-main: `0bc67c6`; werkbranch: `codex/complete-leon`.
- Schone kloon: `/Users/perhorstmanshoff/.codex/worktrees/leon-completion-20260908`.
- Oorspronkelijke gedeelde SSD-kopie blijft bewaard. Die mist kernbestanden en
  meldde bij `git diff --stat` een onleesbaar Git-object.
- Python/SQLite en de bestaande Gaia-vormgeving blijven de basis.
- Kostenvoorkeur eigenaar: lichtere agents voeren afgebakende opdrachten uit;
  hoofdagent coördineert, integreert en controleert. Geen dubbel onderzoek.

## Uitvoeringsvolgorde

1. Duurzame echte chat: gesprekken, expliciete context-/kostenpreview,
   idempotente uitvoering, resultaten en herstel na herladen.
2. Gaia Chat aansluiten; oudere opdrachten rechtstreeks kunnen herstellen.
3. Installatie, start/stop, healthcheck, private backup/restore en Ubuntu-units.
4. Vandaag en Memory aansluiten op werkelijke, herleidbare lokale gegevens.
5. Eén read-only connector met begrensde toegang, bronvermelding en fouttests.
6. Nachtwerk, prioritering en ochtendrapport verbinden met echte uitvoeringen.
7. Ontbrekende specialistische functies volgens implementation-backlog.md;
   externe acties uitsluitend met specifieke bevoegdheid en backendcontrole.
8. Integratie-, browser- en hersteltests; installatie/hardware waar beschikbaar.

## Bewijs en grenzen

Stand 25 september: stappen 1–2 lokaal geïmplementeerd en met offline tests plus
echte browserinteractie tegen een nepmodel gecontroleerd. Stap 3 heeft lokale
scripts en Ubuntu-unitvoorbeelden; doelserveracceptatie blijft open. Stap 4 is
lokaal geïmplementeerd en via browser tegen tijdelijke SQLite gecontroleerd.
Stap 5 is voor de accountloze Open-Meteo-weerbron live voltooid: vaste
Amsterdam-scope, bronvermelding, fouttests, cache en audit zijn op de doel-VM
bewezen. Google Agenda/Gmail blijft apart geblokkeerd op private OAuth-
credentials. Stap 6 heeft begrensde
autonomiestatus, ochtendbrief, optionele dagelijkse lokale bronscan en een
config-gated Firecrawl search-only executor. Researchcontract en disabled-state
zijn offline/browser-getest; live provideracceptatie en self-improvement blijven
open. Self-improvement heeft inmiddels een review-only statische patchvalidator;
uitvoering van gewijzigde code blijft geblokkeerd tot bewezen OS-isolatie.
De echte M40-chat- en text-only agentruntime, wachtwoordlogin, LAN-route en
HTTPS-fallback zijn end-to-end beproefd. Stappen 7–8 blijven open.
Bewijs en actuele aantallen: `handoff.md`,
`chat-browser-evidence.md`, `memory-today-browser-evidence.md`,
`google-browser-evidence.md`, `autonomy-browser-evidence.md`,
`research-browser-evidence.md`, `weather-readonly.md` en `web-validation.md`.

Elke afgeronde stap krijgt relevante regressietests, onafhankelijke review en
een korte handoff. Geen betaalde providercall zonder gekozen budget en concrete
tekstapproval. Ubuntu/M40, persoonlijke accounts en fysieke apparaten vereisen
eigen live verificatie; beschikbaarheid wordt expliciet vermeld.

Volledige productacceptatie blijft open zolang vereiste stappen niet aantoonbaar
zijn voltooid. De actieve goal blijft dan open.
