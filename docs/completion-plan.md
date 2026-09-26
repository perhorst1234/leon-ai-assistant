# Leon afmaken — actuele volgorde, 26 september 2026

De productvisie staat in personal-ai-assistant-plan.md. De nieuwste eigenaar-
instructies geven routineopdrachten, shopper-berichten en lokale teksttaken
ruimte voor automatische uitvoering. Alleen een werkende keten geldt als klaar;
losse klasses, algoritmes of demo's tellen niet als een aangesloten agent.
Bestaande modules hergebruiken; één onderdeel bouwen, gericht testen, werkelijk
beproeven en deployen voordat het volgende onderdeel wordt uitgebreid.

## Wat er nog mist

| Onderdeel van de visie | Werkelijk aanwezig | Nog afmaken |
|---|---|---|
| Personal Agent / chat | Echte M40-chat, automatisch geheugen, lokale achtergrondtaken en vaste tools | Betrouwbare multi-tool-plannen |
| Memory / graph | Bewaren, ophalen, corrigeren, verwijderen, relaties en automatische context | Voorkeuren/correcties vanzelf leren, conflicten netjes behandelen |
| Task Manager | SQLite-taken, wachtrij, checkpoints, herstel, chatuitvoering en terugbezorging | Subtaken en afhankelijkheden |
| Research Agent | Chat → Firecrawl → M40-synthese → bronnen in chat/Werk, max10 credits/dag | Dieper lezen binnen budget en periodieke research |
| Planner / Google | PKCE OAuth, alleen-lezen Agenda/Gmail-adapters | Echte accountconsent, live Agenda, planning en agenda-writes; Gmail is nu metadata, geen volledige mailbox |
| Shopper | Wekelijkse MP/Vinted-zoekopdrachten, echte MP-berichten, delayed replies | Echte inkomende replyketen bewijzen, Vinted-onderhandelingen, TicketSwap-eventwatch en alerts |
| Server Manager | Status, wekelijkse echte inspectie, chatmeldingen en beperkte serviceherstarts | Ruimere diagnose/backups en geverifieerde herstelacties voor andere storingen |
| Model Scheduler | Lokale Qwen/M40, sensitive-local routing, gedeelde GPU-lease en correcte cacherouting | Gezamenlijke prioritering en globale thermische regeling |
| M40 Code Worker | OpenCode/GPT-OSS read/edit/readback eerder live bewezen | Vanuit Leon starten met eigen workspace, daadwerkelijke checks en deployment terugkoppelen |
| Value / Opportunity / Curiosity | Scores, observaties, policies en queue-algoritmes | Relevante echte bronnen, herhaling in eigen gebruik herkennen en bruikbare verbeteringen uitvoeren |
| Night Cycle / Feedback | Dagelijkse veilige bronindex en ochtendbrief | Echte gesprek-/foutreflectie, memory-updates, laag-risicotaken en leerresultaten |
| Zelfverbetering / Genome | Patchvalidator, rollbackcontract, configuratie/journal | Werkende doelhost-uitvoering, tests, succesvolle update en automatische rollback |
| UI / Experience / Character | Eén Werk, compacte Vandaag, echte Chat/Memory | Kaarten passend bij echte tools, zichtbare blokkades en minder demo-restanten |
| Manager / school / reizen | Vooral conceptrollen | Gekozen bronnen en concrete gebruiksscenario's; nog geen financiële/accountacties |

## Bouwvolgorde

1. **Algemene lokale opdrachten uitvoeren — gereed voor teksttaken.** Schrijf-/analyse-/planningstaken
   via chat op de bestaande M40-wachtrij, pauze/hervatten/annuleren en één keer
   terugmelden in het oorspronkelijke gesprek. Resultaten in Werk. Geen betaalde
   providerfallback. Tekst voltooid betekent niet dat externe acties zijn gedaan.
2. **Geheugen in dagelijks gebruik — automatische context gereed.** Relevante bestaande herinneringen in
   gewone gesprekken en taken gebruiken; expliciete correcties/voorkeuren bewaren.
3. **Echte research — live bewezen.** Bestaande Firecrawl-credits, duidelijke daglimiet,
   bronvermelding, lokale synthese en geen nieuwe betaling.
4. **Planner en accounts.** Google-consent afmaken; agenda lezen, plannen en
   de eigenaar-geautoriseerde schrijfacties aansluiten.
5. **Shopper afronden.** Vinted en TicketSwap, echte meldingen en follow-ups;
   het bestaande 64GB-gesprek blijft op pauze, 128GB blijft prioriteit.
6. **Proactieve routines.** Dag-/weekchecks, serverinspectie, ochtendbrief en
   taakherinneringen. Alleen melden bij relevant nieuws of een blokkade.
7. **Code Worker en nachtelijke verbetering.** Bestaande M40-coder inzetten,
   werkende tests/rollback en resultaat terug in Werk; daarna echte reflectie,
   opportunity/curiosity en Genome-updates.
8. **Overige rollen en afronding.** School-/reis-/managerbronnen waar gewenst,
   dynamische kaarten en gezamenlijke herstel-/rebootacceptatie.

## Nog benodigde eigenaargegevens

- Google OAuth: client-ID is bevestigd gelijk aan de server. De echte consent
  en accounttoegang zijn nog niet bewezen; alleen opnieuw verbinden zodra de
  opgeslagen callbacks bij Google actief zijn.
- Research: toestemming voor maximaal tien bestaande Firecrawl-credits per dag
  is gegeven; geen credits kopen en geen OpenAI gebruiken voor synthese.
- TicketSwap: eerste concert/eventlink, aantal tickets en maximale totaalprijs.
- Andere accountrollen: pas toegang vragen wanneer de concrete integratie aan
  de beurt is. Geen abonnementen of nieuwe providers zonder kostenkeuze.

Actuele controles en deployments staan in handoff.md. Publiceer nooit sleutels,
sessies, persoonlijke gesprekken of de database in deze openbare repository.
