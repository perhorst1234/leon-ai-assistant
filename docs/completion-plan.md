# Leon afronden — 8 september 2026

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

Stand 9 september: stappen 1–2 lokaal geïmplementeerd en met offline tests plus
echte browserinteractie tegen een nepmodel gecontroleerd. Stap 3 heeft lokale
  scripts en Ubuntu-unitvoorbeelden; doelserveracceptatie blijft open. Stappen
4–8 blijven open. Bewijs en actuele aantallen: `handoff.md`,
`chat-browser-evidence.md`, `web-validation.md`.

Elke afgeronde stap krijgt relevante regressietests, onafhankelijke review en
een korte handoff. Geen betaalde providercall zonder gekozen budget en concrete
tekstapproval. Ubuntu/M40, persoonlijke accounts en fysieke apparaten vereisen
eigen live verificatie; beschikbaarheid wordt expliciet vermeld.

Volledige productacceptatie blijft open zolang vereiste stappen niet aantoonbaar
zijn voltooid. De actieve goal blijft dan open.
