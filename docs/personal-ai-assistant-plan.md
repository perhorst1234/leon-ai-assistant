# Gaia / Personal AI Assistant — uitgewerkt conceptplan

## 0. Werkelijke projectstatus en overdracht — 6 september 2026

Dit document beschrijft de productvisie; een beschreven functie is niet automatisch gebouwd. De gebruiker wil verder werken op Windows zolang de Linux-server wordt geüpgraded, met GitHub als overdraagbare code- en planversie.

- **Gecontroleerd:** GitHub `main` op `d0f7ba0` bevatte alleen dit plan en `.gitkeep`. Ook de andere remote branch bevatte geen applicatiecode.
- **Bestaande frontend gevonden:** de Gaia-website uit de Codex-taak “Maak AI-assistantwebsite prachtig”, lokale broncommit `f5e8426`. Een bronkopie staat nu in [`apps/web`](../apps/web), met product- en designdocumentatie. Vandaag, Chat, Werk, Memory, agentkeuze en approval-preview zijn gebouwd als interactieve demo.
- **Backend gedeeltelijk teruggevonden:** Python-control-plane met 16 lokale commits en ongecommitte werk. De export mist actuele `server.py`, `store.py` en `test_control_plane.py`; zie [audit](server-recovery-audit.md). 22 aanwezige modules slagen voor syntaxcontrole en 34/34 routeringsevaluaties slagen. Agentuitvoering is nog mock, de OpenAI-adapter dry-run; volledige backendtest is geblokkeerd.
- **Doelhardware:** Ubuntu, NVIDIA Tesla M40 en Intel Xeon E5-2676 v3, waarschijnlijk 16 GB systeem-RAM, eventueel 32 GB. Phase 4 noemt 24 GB VRAM, nog niet gemeten. GPU-runtimes uit sectie 22 blijven te valideren kandidaten. OpenAI API mag korte goedkope taken ondersteunen na budget- en privacyconfiguratie; sleutel blijft buiten GitHub.
- **Actuele uitvoering:** zie [overdracht en inventaris](handoff.md), [werkbacklog](implementation-backlog.md) en [hardwarevoorwaarden](hardware.md). Deze documenten onderscheiden bevestigd, prototype, nog te controleren en gepland werk.

De eigenaar vraagt nu het project stap voor stap af te maken en passend bestaand werk te hergebruiken. De eerste stap is de gedeeltelijke snapshot veiligstellen en de ontbrekende actuele bestanden herstellen. Daarna volgen echte, geteste uitvoering, duurzame taakstatus, Gaia-integratie en begrensde tools/providers; zie de uitvoeringsbacklog. De oorspronkelijke conceptroadmap hieronder blijft behouden als productcontext; zij is geen opdracht om bestaand werk opnieuw te bouwen. “Perfect” betekent hier aantoonbare acceptatiecriteria en zichtbare beperkingen, niet een onbewezen garantie.

## 1. Productvisie

Gaia is de werknaam voor een persoonlijke AI-assistent die niet alleen reageert op vragen, maar zichzelf structureel verbetert. Het systeem bestaat uit een snelle dagelijkse assistent, een zware researchlaag voor complexe taken, een contextuele UI/UX-laag en een nachtelijke verbetercyclus die leert van gesprekken, tools, fouten, kansen en terugkerende patronen.

De assistent moet vier dingen tegelijk kunnen:

1. **Direct helpen** bij eenvoudige vragen en kleine taken.
2. **Diep werken** aan grote opdrachten via gespecialiseerde agents en tools.
3. **Zichzelf verbeteren** door kansen in de buitenwereld en patronen in het eigen gedrag te analyseren.
4. **De juiste interface tonen** voor de taak, samengesteld uit vaste, betrouwbare componenten.

Belangrijk uitgangspunt: de assistent voert niet zomaar alles uit. Nieuwe ideeën, tools, MCP-servers, automatiseringen en verbeteringen gaan eerst door een waardefilter en waar nodig door menselijke goedkeuring.

## 2. Hoofdarchitectuur

```text
                         Gaia Interface
        ┌───────────────────────┬───────────────────────┐
        │                       │                       │
 UI Composition Engine   Assistant Character     Experience Engine
        │                       │                       │
        └───────────────────────┴───────────┬───────────┘
                                            │
                                    Personal Agent
                                            │
          ┌──────────────┬──────────────────┼──────────────────┬──────────────┐
          │              │                  │                  │              │
    Memory Engine   Knowledge Graph   Task Manager      Value Engine     MCP Hub
          │              │                  │                  │              │
          └──────────────┴──────────────────┼──────────────────┴──────────────┘
                                            │
                                    Decision Layer
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    │                                               │
              Live Execution                                  Research Agent
                    │                                               │
                    │              ┌────────────────────────────────┼───────────────┐
                    │              │                                │               │
                    │           Planner                         Workers          Tools
                    │              │                                │               │
                    │          Subtaken                    Browser / Code /   Databases /
                    │                                      Python / Search    Files / APIs
                    │                                               │
                    └────────────────── Resultaat + bronnen ────────┘
                                            │
                              Night Improvement System
                                            │
        ┌──────────────────┬────────────────┼────────────────┬──────────────────┐
        │                  │                │                │                  │
 Opportunity Engine  Curiosity Engine  Feedback Engine  Reflection Engine  Gaia Genome
        │                  │                │                │                  │
        └──────────────────┴────────────────┼────────────────┴──────────────────┘
                                            │
                                      Task Queue
                                            │
                                   Ochtendrapport
```

## 3. Kernprincipes

### 3.1 Eén duidelijke verantwoordelijkheid per component
Elke engine heeft één primaire taak. Daardoor blijft het systeem uitbreidbaar, testbaar en veilig.

### 3.2 Eerst beslissen, dan pas uitvoeren
De Personal Agent mag niet automatisch zware resources gebruiken. Elke vraag gaat door classificatie: intentie, complexiteit, risico, benodigde bronnen, geschatte duur en verwachte waarde.

### 3.3 Waarde boven nieuwsgierigheid
De assistent mag nieuwsgierig zijn, maar niet willekeurig handelen. Opportunity Engine en Curiosity Engine genereren ideeën; de Value Engine beslist of iets de moeite waard is.

### 3.4 Menselijke controle op risicovolle acties
Installaties, codewijzigingen, betalingen, datakoppelingen, e-mailacties, publieke posts en destructieve acties vereisen expliciete goedkeuring.

### 3.5 Traceerbaarheid
Elke belangrijke conclusie, actie en aanbeveling krijgt een reden, bron, score en logregel. Dit maakt debugging, vertrouwen en verbetering mogelijk.

## 4. Componenten

## 4.1 Personal Agent

De Personal Agent is de centrale orkestrator. Hij praat met de gebruiker, begrijpt de vraag en bepaalt welke route nodig is.

**Verantwoordelijkheden:**

- Intentie herkennen.
- Context ophalen uit memory en knowledge graph.
- Beslislaag aanroepen.
- Simpele taken zelf afhandelen.
- Grote taken delegeren aan de Research Agent.
- Resultaten samenvatten in de stijl van de gebruiker.
- Feedback verzamelen na belangrijke taken.

**Doet niet:**

- Willekeurig browsen.
- Zelf tools installeren.
- Lange research uitvoeren zonder taakregistratie.
- Onveilige acties uitvoeren zonder goedkeuring.

## 4.2 Memory Engine

De Memory Engine beheert persoonlijke herinneringen en gebruikscontext.

**Soorten geheugen:**

| Type | Doel | Voorbeelden | Bewaartermijn |
|---|---|---|---|
| Session memory | Lopend gesprek begrijpen | huidige vraag, recente correcties | minuten tot uren |
| Working memory | Lopende taken ondersteunen | projectdoel, checklist, open subtaken | dagen tot weken |
| Long-term memory | Blijvende voorkeuren | schrijftaal, favoriete tools, projecten | maanden of langer |
| Episodic memory | Gebeurtenissen onthouden | gebruiker vroeg op datum X om Y | configureerbaar |
| Negative memory | Weten wat niet werkt | tool gaf slechte resultaten | tot herbeoordeling |

**Pipeline:**

```text
Nieuw gesprek
  ↓
Extractie van feiten, voorkeuren en taken
  ↓
Classificatie: tijdelijk / permanent / gevoelig / irrelevant
  ↓
Deduplicatie
  ↓
Opslaan met confidence-score
  ↓
Periodieke herbeoordeling en opschoning
```

## 4.3 Knowledge Graph

De Knowledge Graph verbindt personen, projecten, tools, interesses, taken, bronnen en beslissingen.

**Voorbeeldrelaties:**

- Gebruiker → werkt aan → AI-assistentproject.
- AI-assistentproject → gebruikt mogelijk → MCP.
- MCP-server → lost op → toolintegratie.
- Browser-tool → vaak gebruikt voor → researchtaken.
- Terugkerende taak → kandidaat voor → automatisering.

**Waarom een graph:**

- Context wordt relationeel in plaats van alleen tekstueel.
- De assistent kan patronen vinden tussen losse gesprekken.
- Opportunity en Curiosity kunnen beoordelen of iets relevant is voor bestaande doelen.

## 4.4 Task Manager

De Task Manager beheert werk dat langer duurt dan één direct antwoord.

**Taken bevatten minimaal:**

- Titel.
- Doel.
- Eigenaar: gebruiker, Personal Agent of Research Agent.
- Status: nieuw, gepland, actief, wacht op goedkeuring, geblokkeerd, klaar, afgewezen.
- Deadline of prioriteit.
- Verwachte waarde.
- Risico-inschatting.
- Bronnen en bewijs.
- Subtaken.
- Resultaat.

**Belangrijk gedrag:**

- Grote opdrachten opsplitsen.
- Werk kunnen pauzeren en hervatten.
- Nachtelijke ideeën niet direct uitvoeren, maar in een queue plaatsen.
- Ochtendrapport maken met voorgestelde acties.

## 4.5 Value Engine

De Value Engine is de filter van het hele systeem.

**Scoremodel:**

```text
Value Score =
  0.30 × tijdswinst
+ 0.20 × relevantie voor huidige doelen
+ 0.15 × herbruikbaarheid
+ 0.15 × kans op succes
+ 0.10 × leerwaarde
+ 0.10 × urgentie
- risico
- kosten
- onderhoudslast
```

**Voorbeeldcriteria:**

| Vraag | Positief signaal | Negatief signaal |
|---|---|---|
| Bespaart dit tijd? | Herhaalde workflow wordt korter | Eenmalige optimalisatie |
| Past dit bij doelen? | Direct verbonden aan actief project | Geen relatie met graph |
| Is het veilig? | Officiële bron, beperkte permissies | Onbekende package, brede toegang |
| Is het onderhoudbaar? | Simpele tool, duidelijke docs | Veel dependencies |
| Is het herbruikbaar? | Kan bij meerdere taken helpen | Alleen nichegebruik |

**Acties per score:**

| Score | Actie |
|---|---|
| 90-100 | Hoogwaardige taak; voorstel met prioriteit |
| 70-89 | Toevoegen aan Night Queue |
| 50-69 | Alleen bewaren als idee |
| 30-49 | Archiveren met lage prioriteit |
| 0-29 | Negeren of afwijzen |

## 4.6 Opportunity Engine

De Opportunity Engine kijkt naar de buitenwereld.

**Bronnen:**

- Nieuwe MCP-servers.
- Nieuwe AI-modellen.
- Nieuwe GitHub-projecten.
- Nieuwe APIs.
- Nieuwe browser- en automationtools.
- Nieuwe papers.
- Nieuwe frameworks voor agents.
- Security advisories voor gebruikte tools.

**Hoofdvraag:**

> Lost dit waarschijnlijk een probleem op dat mijn gebruiker heeft?

**Pipeline:**

```text
Externe bron monitoren
  ↓
Nieuw item detecteren
  ↓
Samenvatten
  ↓
Relateren aan Knowledge Graph
  ↓
Risico en betrouwbaarheid inschatten
  ↓
Value Engine scoren
  ↓
Bij hoge score: taakvoorstel maken
  ↓
Bij risico: menselijke goedkeuring vragen
```

## 4.7 Curiosity Engine

De Curiosity Engine kijkt niet naar de buitenwereld, maar naar het gedrag van de assistent zelf.

**Kernvraag:**

> Waarom doe ik dit steeds opnieuw, en kan ik het slimmer maken?

**Signalen:**

- Dezelfde website wordt vaak geopend.
- Dezelfde uitleg wordt vaak gegeven.
- Dezelfde soort research duurt steeds lang.
- De gebruiker corrigeert vaak hetzelfde punt.
- Een tool faalt vaak.
- Een workflow gebruikt veel handmatige stappen.
- Een bepaalde bron levert consequent goede of slechte resultaten.
- Bepaalde taken eindigen vaak met vervolgvragen.

**Outputs:**

- Voorstel voor nieuwe skill.
- Voorstel voor nieuwe tool.
- Voorstel om een workflow te automatiseren.
- Voorstel om een prompt of beslisregel te verbeteren.
- Voorstel om een ongebruikte plugin te verwijderen.
- Voorstel om documentatie of geheugen bij te werken.

**Pipeline:**

```text
Logs en taakgeschiedenis analyseren
  ↓
Herhalende patronen detecteren
  ↓
Frictie meten: tijd, fouten, vervolgvragen, toolwissels
  ↓
Hypothese maken: wat kan beter?
  ↓
Oplossingsidee formuleren
  ↓
Value Engine scoren
  ↓
Task Manager item aanmaken
```

**Voorbeelden:**

| Observatie | Curiosity-hypothese | Mogelijke actie |
|---|---|---|
| 5 keer dezelfde site bezocht | Er is structureel actuele data nodig | Maak connector of bronprofiel |
| 10 keer dezelfde uitleg gegeven | Gebruiker heeft vaste voorkeur voor format | Maak persoonlijke template |
| Taken duren vaak 30 minuten | Workflow kan worden opgesplitst | Maak standaard research-playbook |
| Tool faalt 4 keer | Tool is onbetrouwbaar | Vervang of beperk tool |
| Veel vervolgvragen | Antwoorden missen beslissingscontext | Voeg standaard assumptions-sectie toe |

## 4.8 MCP Hub

De MCP Hub beheert koppelingen met externe tools en data via gestandaardiseerde integraties.

**Verantwoordelijkheden:**

- Registreren welke MCP-servers beschikbaar zijn.
- Permissies per server beheren.
- Toolkwaliteit meten.
- Nieuwe MCP-servers alleen voorstellen na Value Engine-score.
- Ongebruikte of risicovolle servers markeren.

**Veiligheidslagen:**

- Alleen-lezen standaard.
- Per tool expliciete scopes.
- Approval voor schrijfacties.
- Auditlog van toolgebruik.
- Sandbox waar mogelijk.

## 4.9 Research Agent

De Research Agent voert grote opdrachten uit die niet binnen de Live Cycle passen.

**Wanneer starten:**

- Verwachte duur boven 30 seconden.
- Meerdere bronnen nodig.
- Analyse of synthese nodig.
- Code, data, browser of documenten nodig.
- Hoge onzekerheid.
- Resultaat moet citeerbaar zijn.

**Interne structuur:**

```text
Research Agent
  ↓
Planner
  ↓
Subtaken
  ↓
Worker agents
  ├─ Browser Worker
  ├─ Code Worker
  ├─ Data Worker
  ├─ Source Quality Worker
  └─ Report Writer
  ↓
Synthese
  ↓
Bronnencontrole
  ↓
Rapport aan Personal Agent
```

**Output:**

- Samenvatting.
- Methodologie.
- Belangrijkste bevindingen.
- Bronnen.
- Onzekerheden.
- Aanbevolen vervolgstappen.

## 4.10 Feedback Engine

De Feedback Engine meet of de assistent echt beter wordt.

**Vragen na grote taken:**

- Was de gebruiker tevreden?
- Werd het resultaat gebruikt?
- Waren er veel vervolgvragen?
- Welke bronnen waren nuttig?
- Welke tools waren nutteloos?
- Was de taak sneller dan vorige keren?
- Was menselijke correctie nodig?

**Metrics:**

| Metric | Betekenis |
|---|---|
| Time to useful answer | Hoe snel de gebruiker iets bruikbaars kreeg |
| Follow-up burden | Hoeveel extra vragen nodig waren |
| Source usefulness | Welke bronnen vaak goede output geven |
| Tool reliability | Welke tools vaak slagen of falen |
| User acceptance | Of gebruiker voorstel accepteerde |
| Automation ROI | Tijdswinst door automatisering |

## 4.11 UI Composition Engine

De UI Composition Engine bepaalt welke interface Gaia op elk moment toont. Deze engine maakt geen willekeurige nieuwe schermen, maar stelt bestaande componenten samen op basis van intentie, context, complexiteit en taakfase.

**Verantwoordelijkheden:**

- Taaktype vertalen naar een passende UI-compositie.
- Bepalen welke space nodig is: Chat, Research, Workflow, Memory, Tools of Home.
- Componenten kiezen uit de vaste component library.
- Prioriteit en informatiehierarchie bepalen.
- Motion states kiezen: idle, thinking, acting, waiting, completed of risk.
- Missing Component Protocol activeren als een benodigde component niet bestaat.

**Doet niet:**

- Ad-hoc interfaces genereren.
- Nieuwe componentpatronen verzinnen zonder registratie.
- Veiligheids- of approvalregels omzeilen om een vloeiende UI te behouden.

## 4.12 Assistant Character System

Het Assistant Character System geeft Gaia een zichtbare, consistente aanwezigheid in de interface. Dit is geen decoratie, maar een status- en interactielaag.

**Verantwoordelijkheden:**

- Gaia's staat zichtbaar maken: beschikbaar, denkend, handelend, wachtend of slapend.
- Subtiel bewegen naar relevante componenten.
- Toolgebruik en researchstatus begrijpelijk maken.
- De overgang tussen spaces menselijker en herkenbaarder maken.

**Regel:**

De assistant mag nooit de primaire taak verstoren. De aanwezigheid moet rust geven, niet aandacht opeisen.

## 4.13 Experience Engine

De Experience Engine beoordeelt of een interactie nuttig, duidelijk, snel en prettig was. Dit gaat verder dan inhoudelijke correctheid.

**Verantwoordelijkheden:**

- Meten hoeveel vervolgvragen nodig waren.
- Bijhouden of gebruikers voorgestelde acties accepteren.
- Signaleren wanneer UI te zwaar of juist te beperkt was.
- Curiosity Engine voeden met UX-frictie.
- UI Composition Engine verbeteren met ervaring uit eerdere taken.

## 4.14 Gaia Genome

De Gaia Genome is het interne gedragsprofiel van de assistent. Het bepaalt niet wat Gaia mag doen, maar hoe Gaia zich gedraagt binnen de bestaande veiligheidsgrenzen.

**Traits:**

- Curiosity.
- Initiative.
- Verbosity.
- Creativity.
- Precision.
- Autonomy.

**Belangrijke regel:**

Genome-aanpassingen gebeuren langzaam, uitlegbaar en terugdraaibaar. Expliciete gebruikersvoorkeuren wegen zwaarder dan afgeleide patronen.

## 4.15 Concrete agentrollen uit Notities

De ideeën uit de Apple Notes-notitie **Ai assistant** worden vertaald naar bouwbare rollen. Deze rollen zijn geen losse robots die alles mogen, maar gespecialiseerde werkmodi bovenop dezelfde Memory Engine, Value Engine, Task Manager en MCP Hub.

| Rol | Doel | Mag zelfstandig | Vereist altijd approval |
|---|---|---|---|
| Self Learning Agent | Gesprekken, fouten, herhaling en nieuwe bronnen analyseren | Ideeën samenvatten, toolkandidaten scoren, vragen voorbereiden | Tools installeren, permissies wijzigen, persoonlijke data koppelen |
| Manager Agent | Geld, marktdata, abonnementen en financiële keuzes bewaken | Read-only analyses, budgetoverzicht, markt- en cryptoresearch | Betalen, handelen, geld verplaatsen, abonnementen aanpassen |
| Planner Agent | Routines, agenda, taken, vakanties, school/Magister en mails organiseren | Agenda lezen, conflicten signaleren, conceptplanning maken | Agenda-items schrijven, mails sturen, afspraken bevestigen |
| Shopper Agent | Deals zoeken op Marktplaats, Vinted, TicketSwap en webshops | Prijsalerts, vergelijkingen, conceptberichten, shortlist maken | Berichten versturen, bieden, kopen, betalen, accounts gebruiken |
| Server Manager Agent | Servers, containers, processen, logs en updates bewaken | Status lezen, errors samenvatten, updatevoorstellen maken | Containers herstarten, software installeren, firewall/DNS wijzigen |
| Model Scheduler | Lokaal en extern modelgebruik verdelen | Modelroute kiezen op kosten, snelheid, privacy en VRAM | Nieuwe modellen downloaden, GPU-intensieve jobs starten |
| Tool Builder / Value Engine | Beslissen of een nieuwe tool zelf gebouwd moet worden of hergebruikt kan worden | GitHub/MCP-kandidaten zoeken, scorekaart invullen, backlog-item maken | Code laten draaien, repo's installeren, credentials koppelen |

**Gedragsregels per agent:**

- Read-only is de standaardmodus voor alle gekoppelde accounts.
- Schrijfacties worden opgesplitst in concept, preview, risico-uitleg en expliciete goedkeuring.
- Captcha's, logincontroles en anti-botmaatregelen worden niet omzeild. De assistent mag de gebruiker helpen de officiële flow te volgen, maar niet stiekem beveiligingen passeren.
- Geld, bank, crypto, PayPal, tickets, aankopen, e-mail en serverbeheer hebben een extra approval-laag.
- Elke agent schrijft na een belangrijke taak een korte logregel: wat gebeurde er, welke bron/tool is gebruikt, wat kostte het, wat ging mis, wat kan later beter.
- Nieuwe GitHub-projecten of MCP-servers komen eerst in een evaluatie-backlog met bron, use case, permissies, risico's en onderhoudsstatus.

## 5. De beslislaag

Elke gebruikersvraag gaat door een routingbesluit.

```text
Gebruiker stelt vraag
  ↓
Intentie begrijpen
  ↓
Context ophalen
  ↓
Complexiteit schatten
  ↓
Risico inschatten
  ↓
Waarde en urgentie bepalen
  ↓
Route kiezen
```

## 5.1 Routes

| Route | Wanneer | Voorbeeld |
|---|---|---|
| Direct Answer | Simpel, laag risico, geen bronnen nodig | “Vat dit samen” |
| Quick Tool Use | Kort, tool nodig, laag risico | “Check mijn agenda” |
| Research Agent | Complex, meerdere bronnen, citeerbaar | “Onderzoek beste aanpak” |
| Task Queue | Niet urgent of nachtelijk | “Zoek later optimalisaties” |
| Approval Required | Risicovol of extern effect | “Installeer deze server” |
| Refuse / Redirect | Onveilig of ongepast | Schadelijke actie |

## 5.2 Beslisboom

```text
Vraag ontvangen
  ↓
Is de intentie duidelijk?
  ├─ Nee → korte verduidelijkingsvraag
  └─ Ja
      ↓
Kan dit betrouwbaar binnen 30 seconden?
  ├─ Ja → Personal Agent voert uit
  └─ Nee
      ↓
Is het urgent?
  ├─ Ja → Research Agent starten
  └─ Nee → Task Queue / Night Cycle
      ↓
Heeft de taak externe gevolgen?
  ├─ Ja → goedkeuring vragen
  └─ Nee → uitvoeren volgens route
```

## 6. De drie hoofdcircuits plus reflectielaag

## 6.1 Live Cycle

Doel: snel reageren.

```text
Vraag
  ↓
Begrijpen
  ↓
Beslissen
  ↓
Uitvoeren
  ↓
Antwoord
  ↓
Lichte memory-update
```

**Eigenschappen:**

- Snel.
- Lage kosten.
- Minimale toolcalls.
- Alleen noodzakelijke context.

## 6.2 Research Cycle

Doel: diep werk leveren.

```text
Taak
  ↓
Planner
  ↓
Subtaken
  ↓
Workers
  ↓
Bronnencontrole
  ↓
Rapport
  ↓
Feedback
```

**Eigenschappen:**

- Mag langer duren.
- Werkt met meerdere bronnen.
- Produceert bewijsbaar resultaat.
- Houdt status bij in Task Manager.

## 6.3 Improvement Cycle

Doel: de assistent verbeteren terwijl de gebruiker niet wacht.

```text
22:00 Night Cycle
  ↓
Nieuwe gesprekken ophalen
  ↓
Memory analyseren
  ↓
Knowledge Graph bijwerken
  ↓
Opportunity scan
  ↓
Curiosity scan
  ↓
Value Engine scoren
  ↓
Task Queue bijwerken
  ↓
Ochtendrapport genereren
```

## 6.4 Self Reflection Layer

Doel: reflecteren op eigen gedrag.

```text
Eigen logs
  ↓
Patronen
  ↓
Frictiepunten
  ↓
Hypotheses
  ↓
Verbeterideeën
  ↓
Experimenten
  ↓
Meten of verbetering werkt
```

Deze laag maakt de assistent anders dan een normale chatbot: hij leert niet alleen van nieuwe informatie, maar ook van zijn eigen inefficiënties.

## 7. Night Improvement System

## 7.1 Dagelijkse planning

| Tijd | Actie |
|---|---|
| 22:00 | Night Cycle start |
| 22:05 | Gesprekken en taken verzamelen |
| 22:15 | Memory-analyse |
| 22:30 | Knowledge Graph-update |
| 23:00 | Opportunity scan |
| 23:30 | Curiosity scan |
| 00:00 | Value scoring |
| 00:30 | Task Queue ordenen |
| 01:00 | Veilige laag-risico verbeteringen voorbereiden |
| 07:00 | Ochtendrapport klaarzetten |

## 7.2 Ochtendrapport

Het ochtendrapport bevat:

- Wat gisteren is geleerd.
- Welke herinneringen zijn bijgewerkt.
- Welke kansen zijn gevonden.
- Welke interne patronen zijn ontdekt.
- Welke taken worden voorgesteld.
- Welke acties goedkeuring nodig hebben.
- Welke bronnen of tools minder nuttig bleken.

## 8. Data- en opslagmodel

## 8.1 Entiteiten

| Entiteit | Beschrijving |
|---|---|
| UserPreference | Voorkeuren van de gebruiker |
| Project | Lopend doel of initiatief |
| Task | Actie-item of onderzoek |
| Source | Website, paper, repo, API of document |
| Tool | Tool, MCP-server, script of agentfunctie |
| Observation | Logobservatie uit gedrag |
| Opportunity | Externe kans |
| CuriosityInsight | Intern verbeteridee |
| ValueAssessment | Score en reden |
| FeedbackEvent | Gebruikers- of systeemfeedback |

## 8.2 Belangrijke velden

Elke observatie of aanbeveling krijgt:

- `id`.
- `created_at`.
- `source`.
- `confidence`.
- `risk_level`.
- `value_score`.
- `related_projects`.
- `recommended_action`.
- `approval_required`.
- `expiry_date`.

## 9. Veiligheid, privacy en governance

## 9.1 Veiligheidsregels

- Geen installaties zonder toestemming.
- Geen gevoelige data naar externe tools zonder beleid.
- Geen automatische betalingen.
- Geen publieke communicatie zonder preview.
- Geen destructieve file- of databaseacties zonder goedkeuring.
- Toolpermissies standaard minimaal.
- Auditlog verplicht voor iedere externe actie.

## 9.2 Privacyregels

- Memory moet uitlegbaar en verwijderbaar zijn.
- Gebruiker kan zien wat is onthouden.
- Gevoelige informatie krijgt extra classificatie.
- Verouderde context wordt opgeschoond.
- Niet elke chatregel wordt permanent geheugen.

## 9.3 Evaluatie

Gebruik een risicoraamwerk met minimaal deze categorieën:

- Betrouwbaarheid.
- Veiligheid.
- Privacy.
- Transparantie.
- Controleerbaarheid.
- Bias en verkeerde aannames.
- Kostenbeheersing.

## 10. Bronnenpipeline

## 10.1 Brontypen

| Bron | Gebruik |
|---|---|
| Officiële documentatie | Hoogste prioriteit voor APIs, SDKs en protocollen |
| GitHub repositories | Nieuwe tools, issues, releases, adoptie |
| Papers | Nieuwe technieken en evaluatiemethoden |
| Security advisories | Kwetsbaarheden en risico's |
| Product changelogs | Nieuwe functies en breaking changes |
| Eigen logs | Curiosity Engine en feedback |
| Gebruikersfeedback | Prioriteiten en kwaliteit |

## 10.2 Bronbeoordeling

Elke bron krijgt een score:

```text
Source Score = autoriteit + actualiteit + reproduceerbaarheid + relevantie - bias - onzekerheid
```

## 10.3 Bronhiërarchie

1. Officiële specificaties en documentatie.
2. Publicaties van de maker van het product.
3. Peer-reviewed papers of erkende onderzoeksinstituten.
4. Repositories met actieve maintainers.
5. Betrouwbare technische blogs.
6. Communityposts, alleen als signaal en niet als definitief bewijs.

## 11. Voorbeelden van end-to-end flows

## 11.1 Simpele livevraag

```text
Gebruiker: “Maak dit korter.”
  ↓
Personal Agent herkent simpele schrijftaak
  ↓
Geen Research Agent nodig
  ↓
Antwoord direct
  ↓
Memory: stijlvoorkeur eventueel bijwerken
```

## 11.2 Grote researchtaak

```text
Gebruiker: “Onderzoek welke MCP-servers nuttig zijn voor mijn workflow.”
  ↓
Decision Layer: complex + bronnen nodig
  ↓
Research Agent start
  ↓
Planner maakt criteria
  ↓
Browser Worker zoekt officiële bronnen en repositories
  ↓
Source Quality Worker beoordeelt betrouwbaarheid
  ↓
Value Engine scoort per MCP-server
  ↓
Rapport met aanbevelingen
  ↓
Task Manager zet installaties op approval
```

## 11.3 Night Cycle met Opportunity

```text
Nieuwe MCP-server gevonden
  ↓
Opportunity Engine vat samen
  ↓
Knowledge Graph matcht met actief project
  ↓
Value Engine ziet hoge tijdswinst
  ↓
Task Queue: “Evalueer deze MCP-server”
  ↓
Ochtendrapport vraagt toestemming
```

## 11.4 Night Cycle met Curiosity

```text
Logs tonen: dezelfde website 8 keer bezocht
  ↓
Curiosity Engine maakt hypothese
  ↓
“Gebruiker heeft vaak actuele data van deze site nodig”
  ↓
Value Engine berekent tijdswinst
  ↓
Task Queue: “Maak bronprofiel of connectorvoorstel”
  ↓
Ochtendrapport toont voorstel
```

## 11.5 Voorbeelden uit Notities

Deze voorbeelden komen uit de Apple Notes-notitie **Ai assistant** en maken het plan concreet.

### WK-wedstrijden in de agenda zetten

```text
Gebruiker:
Kan je alle WK-wedstrijden in mijn calendar zetten?
  ↓
Planner Agent zoekt betrouwbare wedstrijdbron
  ↓
Bronnen worden vergeleken: officiële kalender, openfootball/worldcup.json, ICS-feed
  ↓
Gaia toont preview: aantal wedstrijden, tijdzone, kalendernaam, dubbele items
  ↓
Gebruiker geeft approval
  ↓
Calendar-tool schrijft events
  ↓
Task Manager bewaart bron en update-regel
```

Belangrijk: agenda-items worden nooit zonder preview geschreven.

### Reisresearch terwijl de gebruiker Gaia niet actief gebruikt

```text
Gebruiker vraagt over vliegtickets of Airbnb's op een plek
  ↓
Live Cycle geeft direct antwoord op de vraag
  ↓
Task Manager maakt optionele researchtaak
  ↓
Night Cycle onderzoekt stranden, bezienswaardigheden, Airbnb-zones, reistijd en budget
  ↓
Research Agent bewaart bronnen en shortlist
  ↓
Ochtendrapport toont: "Ik heb extra reisresearch klaarstaan"
```

Belangrijk: de assistent koopt geen tickets, boekt geen verblijf en stuurt geen berichten zonder expliciete approval.

### Weather-tool faalt en Gaia repareert de workflow

```text
Gebruiker:
Wat is het weer in Amsterdam?
  ↓
Weather-tool faalt of geeft onduidelijk resultaat
  ↓
Feedback Engine logt tool failure
  ↓
Curiosity Engine ziet patroon of hoge frictie
  ↓
Tool Builder zoekt alternatief: andere weather API, MCP-server of fallbackbron
  ↓
Value Engine beoordeelt betrouwbaarheid, kosten en onderhoud
  ↓
Task Queue: "Verbeter weather-workflow"
```

Belangrijk: Gaia probeert niet eindeloos dezelfde fout opnieuw, maar maakt een reparatietaak met diagnose.

### Shopper-deal vinden

```text
Gebruiker:
Zoek een goede deal voor X op Marktplaats/Vinted/TicketSwap
  ↓
Shopper Agent maakt filters: prijs, locatie, conditie, maat, deadline
  ↓
Read-only search via scraper/API/browser
  ↓
Resultaten worden gescoord: prijs, betrouwbaarheid, afstand, verkoper, timing
  ↓
Gaia toont shortlist en eventueel conceptbericht
  ↓
Bericht, bod, reservering of aankoop alleen na approval
```

Belangrijk: bij marktplaatsen en tickets blijft Gaia binnen officiële loginflows en respecteert rate limits. Geen captcha-bypass, geen proxyrotatie om blokkades te ontwijken en geen automatische aankoop.

### Wekelijkse servercheck

```text
Wekelijkse planning
  ↓
Server Manager Agent leest status van containers, logs, uptime en diskruimte
  ↓
Errors worden samengevat met ernst en mogelijke oorzaak
  ↓
Updates worden voorgesteld, niet direct uitgevoerd
  ↓
Gebruiker keurt concrete acties goed
  ↓
Ansible/Portainer/Docker-tools voeren wijzigingen uit
```

Belangrijk: monitoring mag automatisch; wijzigingen aan draaiende services blijven approval-first.

## 12. Roadmap zonder coderen

### Fase 1 — Hersenen definiëren

**Doel:** alle componenten en verantwoordelijkheden scherp krijgen.

**Deliverables:**

- Componentkaart.
- Verantwoordelijkheidsmatrix.
- Datamodel op hoofdlijnen.
- Beslisregels voor Live vs Research.
- Eerste Value Engine-scorekaart.

### Fase 2 — Beslislaag ontwerpen

**Doel:** voorkomen dat zware agents onnodig worden gebruikt.

**Deliverables:**

- Intentietaxonomie.
- Complexiteitsscore.
- Risicomatrix.
- Routebeslisboom.
- Escalatieregels.

### Fase 3 — Memory en Knowledge Graph ontwerp

**Doel:** context betrouwbaar organiseren.

**Deliverables:**

- Memorytypen.
- Retentiebeleid.
- Graph-entiteiten en relaties.
- Confidence- en expiryregels.
- Privacyregels.

### Fase 4 — Night Improvement System ontwerp

**Doel:** automatische nachtelijke verwerking specificeren.

**Deliverables:**

- Night Cycle schema.
- Ochtendrapport-template.
- Task Queue-regels.
- Feedbackmetingen.
- Approvalbeleid.

### Fase 5 — Opportunity Engine ontwerp

**Doel:** externe kansen vinden zonder willekeur.

**Deliverables:**

- Bronlijst.
- Scanfrequenties.
- Relevantiecriteria.
- Source scoring.
- Opportunity-template.

### Fase 6 — Curiosity Engine ontwerp

**Doel:** interne frictie en herhaling omzetten in verbeterideeën.

**Deliverables:**

- Logsignalen.
- Frictiemetrics.
- Patroondetectieregels.
- CuriosityInsight-template.
- Experiment- en evaluatieregels.

### Fase 7 — Value Engine verfijnen

**Doel:** alle ideeën, taken en tools objectief prioriteren.

**Deliverables:**

- Definitieve scoreformule.
- Risicodrempels.
- Kostenmodel.
- ROI-model.
- Besluitregels per scoreband.

### Fase 8 — Research Agent specificeren

**Doel:** diepe taken zelfstandig laten plannen en uitvoeren.

**Deliverables:**

- Planner-specificatie.
- Workerrollen.
- Rapportformat.
- Bronnencontrole.
- Stop- en approvalcriteria.

### Fase 9 — Governance en evaluatie

**Doel:** vertrouwen, veiligheid en kwaliteit borgen.

**Deliverables:**

- Auditlogbeleid.
- Privacybeleid.
- Toolpermission-model.
- Evaluatieset.
- Incident- en rollbackproces.

## 13. Minimale eerste versie

Een goede eerste niet-code MVP is een set documenten en beslismodellen:

1. Architectuurdiagram.
2. Componentdefinities.
3. Beslisboom.
4. Value Engine-scorekaart.
5. Opportunity-template.
6. Curiosity-template.
7. Night Cycle-template.
8. Ochtendrapport-template.
9. Security- en approvalregels.
10. Researchrapport-template.
11. UI/UX-principes.
12. Design language.
13. Component library-specificatie.
14. Component DNA-model.
15. Voorbeeldschermen en voorbeeldflows.
16. Gaia Constitution als single source of truth.

Pas daarna is het verstandig om te coderen.

## 14. Gaia Constitution

Het project verdient een eigen constitution: een stabiel handboek dat bepaalt hoe Gaia denkt, handelt, onthoudt, leert en verschijnt in de interface. Dit voorkomt dat het systeem na tientallen wijzigingen langzaam verandert in een verzameling losse features.

De constitution is geen marketingdocument. Het is de bron van waarheid voor productkeuzes, architectuur, UI/UX, toolgebruik, memory, veiligheid en zelfverbetering.

## 14.1 Kernwetten

**Wet 1: Gaia bestaat om het leven van de gebruiker beter te maken door intelligentie, niet door feature-count.**

Nieuwe functies zijn alleen goed als ze tijd besparen, frictie verlagen, kwaliteit verhogen of continuiteit verbeteren.

**Wet 2: Gaia denkt voordat Gaia handelt.**

Elke actie volgt minimaal deze volgorde:

```text
Intentie begrijpen
  ↓
Context ophalen
  ↓
Confidence inschatten
  ↓
Waarde en risico inschatten
  ↓
Minimale route kiezen
  ↓
Uitvoeren of toestemming vragen
```

**Wet 3: Gaia verbetert zichzelf zonder haar identiteit kwijt te raken.**

Het systeem mag leren, maar de persoonlijkheid, stijl en veiligheidsprincipes blijven herkenbaar.

**Wet 4: Gaia genereert geen willekeurige interfaces.**

Gaia componeert interfaces uit handgemaakte, geteste componenten. De AI kiest layout, inhoud, prioriteit en staat; de component library bepaalt vorm, gedrag en toegankelijkheid.

**Wet 5: Elke betekenisvolle interactie maakt Gaia slimmer.**

Niet elke zin wordt opgeslagen, maar elke taak kan leiden tot betere memory, betere routing, betere skills, betere UI of betere toolselectie.

## 14.2 Constitution-map

Een professionele documentatiestructuur voor Gaia kan er zo uitzien:

```text
Gaia Constitution/
│
├── 00 Mission.md
├── 01 Philosophy.md
├── 02 Architecture.md
├── 03 Intelligence.md
├── 04 Memory.md
├── 05 Knowledge Graph.md
├── 06 Tasks.md
├── 07 Tools and MCP.md
├── 08 Research Agent.md
├── 09 Opportunity Engine.md
├── 10 Curiosity Engine.md
├── 11 Value Engine.md
├── 12 Reflection.md
├── 13 UI Engine.md
├── 14 Design Language.md
├── 15 Component Library.md
├── 16 Component DNA.md
├── 17 Assistant Character.md
├── 18 Experience Engine.md
├── 19 Safety and Governance.md
├── 20 Development Standards.md
└── 21 Roadmap.md
```

Voor de eerste fase hoeft dit nog niet als losse bestanden te bestaan. Het belangrijkste is dat deze onderwerpen inhoudelijk zijn gedefinieerd voordat er code wordt geschreven.

## 14.3 Twee hersenen

Gaia heeft een bewust en een onderbewust systeem.

| Brein | Doel | Zichtbaar voor gebruiker | Voorbeelden |
|---|---|---|---|
| Conscious Brain | Realtime interactie | Ja | chat, snelle acties, UI-status, toolbeslissingen |
| Subconscious Brain | Reflectie en groei | Alleen via rapporten | memory compressie, skillvorming, graph-updates, night cycle |

**Conscious Brain:**

- Reageert direct.
- Houdt de gebruiker op de hoogte.
- Kiest de snelste betrouwbare route.
- Start Research Agent alleen als dat echt nodig is.
- Toont voortgang, bronnen en keuzes in de UI.

**Subconscious Brain:**

- Draait in de Night Improvement System.
- Zoekt patronen in gedrag.
- Combineert herinneringen.
- Schrijft verbeterideeën.
- Maakt skillvoorstellen.
- Schoont oude of zwakke context op.

## 14.4 Gaia Genome

Gaia krijgt een intern afstemmingsmodel: geen simpele instellingenpagina, maar een gedragssysteem dat langzaam meebeweegt met de gebruiker.

| Trait | Betekenis | Laag | Hoog |
|---|---|---|---|
| Curiosity | Hoe actief Gaia patronen onderzoekt | Wacht af | Zoekt actief verbeterkansen |
| Initiative | Hoe snel Gaia voorstellen doet | Alleen op verzoek | Komt proactief met suggesties |
| Verbosity | Hoe uitgebreid antwoorden zijn | Kort | Uitvoerig |
| Creativity | Hoe vrij Gaia alternatieven bedenkt | Conservatief | Experimenteel |
| Precision | Hoe streng Gaia verifieert | Snel genoeg | Bron- en detailgericht |
| Autonomy | Hoe zelfstandig Gaia werkt | Veel toestemming | Meer eigen planning |

Voorbeeldprofiel:

```text
Curiosity   ███████░░░  0.70
Initiative  ██████░░░░  0.60
Verbosity   ████░░░░░░  0.40
Creativity  ███████░░░  0.70
Precision   █████████░  0.90
Autonomy    █████░░░░░  0.50
```

De genome verandert niet willekeurig. Aanpassing gebeurt op basis van feedback, acceptatiegraad, taakgeschiedenis en expliciete gebruikersvoorkeuren.

## 14.5 Evolution Journal

Elke week schrijft Gaia een intern evolution journal. Dit maakt groei zichtbaar en controleerbaar.

Voorbeeld:

```text
Week 28

Geleerd:
- De gebruiker werkt vaak aan AI-assistentarchitectuur en UI-systemen.
- De gebruiker wil eerst sterke documentatie voordat er code komt.
- Lange antwoorden zijn acceptabel als ze structuur en bouwbaarheid geven.

Verbeteringen:
- Research-routing aangescherpt voor architectuurtaken.
- Curiosity Engine moet herhaalde ontwerpvragen herkennen.
- UI-specificaties moeten voortaan Component DNA bevatten.

Nieuwe skill-kandidaat:
- Gaia Product Architecture Skill

Te verwijderen of te beperken:
- Geen.

Open vragen:
- Wil de gebruiker Gaia primair als desktop-app, browserlaag of webapp?
```

Het journal is geen chatlog. Het is een samenvatting van groei, hypotheses en systeemverbeteringen.

## 15. UI/UX-visie

Gaia moet niet voelen als een gewone chat-app of SaaS-dashboard. De interface moet voelen als een rustige, levende werkomgeving waarin de assistent zichtbaar denkt, taken organiseert en context opbouwt.

De stijlrichting:

- Premium en minimalistisch.
- Rustig, intelligent en persoonlijk.
- Fluid zoals een moderne browser- of OS-interface.
- AI-native: de UI past zich aan intentie, context en taakfase aan.
- Geen druk dashboard met overal widgets.
- Geen willekeurige AI-gegenereerde schermen.

## 15.1 UX-doelen

| Doel | Betekenis in de praktijk |
|---|---|
| Snelheid | Simpele taken mogen niet door zware UI of research worden vertraagd |
| Vertrouwen | Gaia toont waarom iets gebeurt, welke bronnen gebruikt zijn en wat goedkeuring nodig heeft |
| Continuiteit | Projecten, taken en memories voelen verbonden over dagen en weken |
| Focus | De gebruiker ziet maximaal 1-3 primaire dingen tegelijk |
| Controle | Autonomie is zichtbaar, pauzeerbaar en begrensd |
| Groei | Verbeteringen zijn zichtbaar via ochtendrapporten en evolution journal |

## 15.2 UI als compositie, niet als generatie

Gaia bouwt geen nieuwe UI per prompt. Gaia kiest uit bestaande bouwblokken.

```text
Gebruikersintentie
  ↓
Taaktype bepalen
  ↓
Benodigde informatie bepalen
  ↓
Componenten kiezen
  ↓
Layout samenstellen
  ↓
Animatiestaat kiezen
  ↓
Gebruiker ziet contextuele interface
```

Voorbeelden:

| Intentie | UI-compositie |
|---|---|
| Snelle vraag | Chat Space + compacte contextkaart |
| Grote research | Research Board + bronnenkolom + voortgangstimeline |
| Workflow bouwen | Canvas + workflow nodes + inspector |
| Memory bekijken | Memory Graph + filterpaneel + detailkaart |
| Night report | Morning Brief + task queue + approval actions |
| Tool installeren | Tool Card + risico-overzicht + approval sheet |

## 15.3 Kernprincipe: bewust weinig tegelijk

De interface mag rijk zijn, maar niet alles tegelijk tonen. Gaia moet informatie progressief ontvouwen.

```text
Eerst:
  Eén helder antwoord of één primaire actie

Daarna:
  Bronnen, redenatie, alternatieven en details op aanvraag

Bij complex werk:
  Status, planning en bewijs zichtbaar houden
```

## 16. Information Architecture

Gaia bestaat uit ruimtes in plaats van klassieke pagina's.

| Space | Doel | Primaire componenten |
|---|---|---|
| Home Space | Startpunt en dagoverzicht | Morning Brief, active tasks, suggestions |
| Chat Space | Direct gesprek | Chat stream, context cards, quick actions |
| Research Space | Diep werk | Research board, source stack, timeline |
| Workflow Space | Automatiseringen en taakstromen | Node canvas, inspector, run history |
| Memory Space | Wat Gaia weet | Memory graph, memory cards, edit controls |
| Knowledge Space | Projecten en relaties | Graph view, entity inspector, relation list |
| Opportunity Space | Externe kansen | Opportunity cards, source evidence, value scores |
| Curiosity Space | Interne verbeteringen | Pattern cards, friction metrics, experiments |
| Tool Space | MCP en integraties | Tool registry, permissions, reliability |
| Settings Space | Grenzen en voorkeuren | Genome controls, privacy, approvals |

Navigatie gebeurt via een compacte floating dock. Geen klassieke permanente sidebar als hoofdpatroon.

## 16.1 Home Space

De Home Space is het dagelijkse commandocentrum.

Moet tonen:

- Wat vraagt vandaag aandacht?
- Welke taken lopen?
- Wat heeft Gaia geleerd?
- Welke acties wachten op goedkeuring?
- Welke kansen zijn gevonden?
- Welke workflows zijn verbeterbaar?

Voorbeeld:

```text
┌─────────────────────────────────────────────────────────────┐
│ Gaia                                      07:42              │
│                                                             │
│ Goedemorgen. Er zijn 3 dingen die aandacht verdienen.        │
│                                                             │
│ ┌ Morning Brief ──────────────────────────────────────────┐ │
│ │ 1. AI-assistentplan uitgebreid met UI/UX-richting        │ │
│ │ 2. Nieuwe opportunity: MCP-tooling voor documenttaken    │ │
│ │ 3. Curiosity: je vraagt vaak om constitution-style docs   │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ┌ Active Tasks ┐   ┌ Approval Needed ┐   ┌ Learned ┐        │
│ │ Research     │   │ Install tool?   │   │ 5 memory updates │
│ │ UI spec      │   │ Review first    │   │ 1 skill idea     │
│ └──────────────┘   └─────────────────┘   └─────────┘        │
│                                                             │
│        Dock: Home | Chat | Research | Memory | Tools         │
└─────────────────────────────────────────────────────────────┘
```

## 16.2 Chat Space

De Chat Space blijft snel en menselijk. Het is niet de plek waar alle complexiteit zichtbaar moet zijn.

Bestaat uit:

- Gesprek.
- Compacte contextkaarten.
- Snelle acties.
- Statusindicator van Gaia.
- Mogelijkheid om een antwoord uit te klappen naar bronnen, taken of memory.

Gedrag:

- Bij simpele vragen blijft de UI compact.
- Bij complexe vragen verschijnt een routekaart: direct, research, queue of approval.
- Bij onzekerheid toont Gaia kort wat ontbreekt.

## 16.3 Research Space

De Research Space is zichtbaar zodra een taak te groot is voor live beantwoording.

Moet tonen:

- Doel van de research.
- Planning.
- Subtaken.
- Bronnen.
- Bewijsstatus.
- Open onzekerheden.
- Verwachte oplevering.

Voorbeeldlayout:

```text
┌ Research Space ──────────────────────────────────────────────┐
│ Vraag: Onderzoek beste MCP-servers voor mijn workflow         │
│ Status: bronnen verzamelen                                    │
│                                                              │
│ ┌ Plan ───────────────┐ ┌ Source Stack ────────────────────┐ │
│ │ 1. Criteria maken   │ │ Officiële docs       betrouwbaar │ │
│ │ 2. Repos zoeken     │ │ GitHub repo          actief      │ │
│ │ 3. Risico scoren    │ │ Changelog            recent      │ │
│ │ 4. Advies schrijven │ │ Community post       signaal     │ │
│ └─────────────────────┘ └──────────────────────────────────┘ │
│                                                              │
│ ┌ Findings Timeline ───────────────────────────────────────┐ │
│ │ 10:05 criteria klaar                                      │ │
│ │ 10:12 8 kandidaten gevonden                               │ │
│ │ 10:18 3 kandidaten afgewezen wegens brede permissies       │ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## 16.4 Memory Space

Memory moet uitlegbaar en bewerkbaar zijn. De gebruiker moet nooit het gevoel krijgen dat Gaia in het geheim een vaag profiel opbouwt.

Views:

- Graph view: relaties tussen projecten, voorkeuren, tools en skills.
- Timeline view: wanneer iets geleerd is.
- Review queue: nieuwe of gevoelige memories die goedkeuring vragen.
- Edit panel: wijzigen, verwijderen, verlagen in confidence of tijdelijk maken.

Memorykaart:

```text
Memory
Type: Preference
Content: Gebruiker wil eerst documentatie voordat er code wordt geschreven.
Confidence: 0.91
Source: 3 gesprekken
Linked to: Gaia project, development workflow
Expires: herbeoordeling over 90 dagen
Actions: keep | edit | make temporary | delete
```

## 17. Component Library

De component library is de visuele grammatica van Gaia. De AI mag componenten kiezen en combineren, maar niet zomaar nieuwe componenten verzinnen.

## 17.1 Basisset componenten

| Component | Doel | Typische plek |
|---|---|---|
| App Shell | Hoofdframe, dock, globale status | alle spaces |
| Floating Dock | Navigatie tussen spaces | onder of zijkant |
| Assistant Entity | Zichtbare AI-aanwezigheid | alle spaces |
| Command Bar | Snel iets vragen of starten | Home, Chat, Workflow |
| Chat Stream | Gesprek | Chat Space |
| Context Card | Compacte relevante context | Chat, Home |
| Task Card | Taakstatus en acties | Home, Research |
| Task Queue | Wachtrij van acties | Home, Task view |
| Research Board | Plan, subtaken, bronnen | Research Space |
| Source Stack | Bronnen met kwaliteitsscore | Research Space |
| Value Score Card | Waarom iets waardevol is | Opportunity, Approval |
| Approval Sheet | Menselijke toestemming | Tools, Tasks |
| Memory Card | Uitlegbaar geheugenitem | Memory Space |
| Memory Graph | Relaties tonen | Memory, Knowledge |
| Workflow Node | Automatiseringsstap | Workflow Space |
| Inspector Panel | Detailinstellingen | Workflow, Graph |
| Morning Brief | Ochtendrapport | Home |
| Evolution Journal Card | Wekelijkse groei | Home, Reflection |
| Genome Panel | Gedragsinstellingen | Settings |

## 17.2 Component DNA

Elke component krijgt metadata, zodat Gaia weet wanneer en hoe hij gebruikt mag worden.

Voorbeeld:

```yaml
component: WorkflowNode
purpose: Visualiseer een stap in een workflow of automatisering
complexity: medium
supports:
  - dragging
  - grouping
  - execution_state
  - inline_errors
compatible_with:
  - WorkflowCanvas
  - InspectorPanel
  - Timeline
  - ApprovalSheet
states:
  - idle
  - selected
  - running
  - waiting_for_approval
  - failed
  - completed
accessibility:
  keyboard: true
  screen_reader_label_required: true
  reduced_motion_variant: true
ai_rules:
  use_when:
    - task_has_steps
    - user_builds_automation
    - workflow_needs_visual_debugging
  avoid_when:
    - task_is_simple_text_answer
    - fewer_than_two_steps_exist
missing_component_fallback:
  fallback: TaskCard
  log_gap: true
```

## 17.3 Missing Component Protocol

Als Gaia een UI nodig heeft die nog niet bestaat:

```text
Benodigde UI bestaat niet
  ↓
Dichtstbijzijnde bestaande component kiezen
  ↓
Gedrag tijdelijk aanpassen
  ↓
Ontbrekende component loggen
  ↓
Value Engine score berekenen
  ↓
Alleen bij hoge waarde voorstel maken
```

Voorbeeld:

| Nodig | Fallback | Voorstel |
|---|---|---|
| Ruimtelijke Home Assistant-map | Device Grid | Room Map Component |
| Live code execution graph | Timeline + Task Cards | Execution Graph Component |
| Memory conflict resolver | Approval Sheet | Memory Diff Component |

## 18. Design Language

## 18.1 Visuele richting

Gaia voelt als:

- Apple-level rust en premium afwerking.
- Arc-achtige vloeiende navigatie.
- Een AI-native interface die leeft zonder druk te worden.
- Een persoonlijke werkomgeving, niet een standaard dashboard.

Niet:

- Druk.
- Speels als een game.
- Een klassiek adminpaneel.
- Een verzameling losse widgets.
- Een chatvenster met decoratie eromheen.

## 18.2 Kleur en materiaal

Basis:

- Donkere en lichte modus vanaf het begin ontwerpen.
- Neutrale basis met zachte diepte.
- Subtiele glass-layers alleen waar het informatiehierarchie helpt.
- Geen schreeuwerige gradients als hoofdidentiteit.

State-accenten:

| Staat | Accent | Gebruik |
|---|---|---|
| Idle | blauw | rustige aanwezigheid |
| Thinking | violet | focus en redenering |
| Acting | cyaan | toolgebruik of uitvoering |
| Waiting | amber | toestemming of input nodig |
| Risk | rood | risico, fout of blokkade |
| Completed | groen | afgerond of gevalideerd |

## 18.3 Typografie en dichtheid

Regels:

- Grote typografie alleen voor echte focusmomenten.
- Compacte panels gebruiken rustige, kleinere headings.
- Geen overvolle tabellen als startpunt.
- Belangrijke scores en statussen moeten scanbaar zijn.
- Lange uitleg moet inklapbaar zijn.

## 18.4 Motion language

Animatie is functioneel, niet decoratief.

Regels:

- Geen harde page reloads als primair patroon.
- Panels morph-en vanuit hun oorsprong.
- Kaarten groeien naar detailviews.
- Taken tonen voortgang met subtiele state changes.
- Reduced motion moet altijd mogelijk zijn.

Voorbeelden:

| Interactie | Motion |
|---|---|
| Task openen | kaart groeit naar inspector |
| Research starten | chatcontext morphs naar Research Board |
| Approval nodig | sheet komt vanuit relevante actie |
| Memory opslaan | kleine pulse op Memory Graph |
| Night report openen | cards verschijnen in prioriteitsvolgorde |

## 18.5 Assistant Character

Gaia krijgt een zichtbare entiteit, maar geen realistische humanoid. De assistent is een zachte digitale aanwezigheid die de systeemstaat communiceert.

States:

| Staat | Gedrag | Betekenis |
|---|---|---|
| Idle | subtiel zweven of ademen | beschikbaar |
| Thinking | focus glow, kleine vertraging | redeneren |
| Acting | beweegt naar relevant component | voert actie uit |
| Waiting | blijft bij approval of vraag | gebruiker moet kiezen |
| Sleeping | gedimde aanwezigheid | night cycle of rust |

Belangrijk: de assistant is onderdeel van de interface, niet alleen decoratie. Als Gaia bronnen verzamelt, mag de entiteit subtiel richting Source Stack bewegen. Als Gaia een workflow uitvoert, mag hij langs de nodes bewegen.

## 18.6 Toegankelijkheid

De levende interface mag toegankelijkheid niet breken.

Regels:

- Alles werkt met toetsenbord.
- Alle interactieve componenten hebben duidelijke namen.
- Motion heeft reduced-motion alternatieven.
- Kleur is nooit de enige informatiedrager.
- Focus states zijn zichtbaar.
- Approval-acties zijn expliciet en niet verstopt in animatie.
- Memory en privacy-acties zijn altijd vindbaar.

## 19. Experience Engine

De Experience Engine beoordeelt niet alleen inhoudelijke kwaliteit, maar ook hoe goed de interactie voelde.

## 19.1 Experience score

```text
Experience Score =
  0.25 × usefulness
+ 0.20 × clarity
+ 0.15 × speed
+ 0.15 × trust
+ 0.10 × UI fit
+ 0.10 × interaction comfort
+ 0.05 × delight
- cognitive load
- unnecessary interruption
```

## 19.2 Signalen

| Signaal | Mogelijke conclusie |
|---|---|
| Gebruiker vraagt veel verduidelijking | Antwoord was niet concreet genoeg |
| Gebruiker accepteert voorstel direct | Routing en presentatie waren goed |
| Gebruiker sluit panel meteen | UI was te zwaar of irrelevant |
| Gebruiker opent bronnen | Transparantie was nuttig |
| Gebruiker corrigeert memory | Memory confidence moet omlaag |
| Gebruiker gebruikt workflow opnieuw | Automatisering heeft waarde |

## 19.3 UX-feedback naar engines

```text
Interaction result
  ↓
Experience score
  ↓
Feedback Engine
  ↓
Memory update / Skill update / UI rule update
  ↓
Curiosity Engine zoekt patronen
```

## 20. Voorbeeld: hoe Gaia moet werken

Dit voorbeeld laat zien hoe de assistent zich gedraagt bij een grote opdracht zoals: “Werk mijn Gaia-concept verder uit met UI/UX en maak het bouwbaar.”

## 20.1 Stap 1: gebruiker vraagt iets groots

```text
Gebruiker:
Kan je het conceptplan verder uitwerken en UI/UX toevoegen?
```

Gaia doet niet meteen alsof het een simpele chatvraag is.

Intern:

```text
Intentie: productarchitectuur + UX-specificatie
Complexiteit: hoog
Bronnen nodig: bestaand plan + voorbeeldtekst + UI/UX-bronnen
Risico: laag, want alleen documentatie
Route: directe documentbewerking met research-light
Memory: gebruiker wil eerst geen code
Output: uitgebreid docs-plan met voorbeeldschermen
```

UI:

```text
Chat Space
  ↓
Compacte routekaart verschijnt:
  - Ik lees het bestaande plan
  - Ik verwerk je Gaia Constitution-voorbeeld
  - Ik voeg UI/UX, componenten en voorbeeldflows toe
  - Ik controleer het document
```

## 20.2 Stap 2: Gaia opent context

In plaats van de gebruiker te overspoelen toont Gaia alleen relevante context:

```text
┌ Context Card ─────────────────────────────┐
│ Gevonden documenten                        │
│ - personal-ai-assistant-plan.md            │
│ - pasted Gaia Constitution voorbeeld       │
│                                            │
│ Belangrijk patroon                         │
│ Je wil Gaia als living AI companion OS,    │
│ niet als gewone chat-app.                  │
└────────────────────────────────────────────┘
```

## 20.3 Stap 3: Research-light en compositie

Omdat dit geen urenlange marktstudie is, start Gaia geen zware Research Agent. Wel gebruikt Gaia lichte broncontrole voor UI-principes.

```text
Decision Layer:
Kan dit betrouwbaar binnen een korte documenttaak?
  Ja
Heeft het externe actuele claims?
  Alleen bronnenlinks
Actie:
  Verifieer relevante UI/accessibility bronnen
```

UI:

```text
Source Stack
- Apple Human Interface Guidelines
- Material Design Motion
- WCAG 2.2
- WAI-ARIA APG
```

## 20.4 Stap 4: document groeit, UI morphs

Tijdens het werk verandert de interface van chat naar documentwerk:

```text
Chat Stream
  ↓ morph
Document Workspace
  ├─ Outline Panel
  ├─ Current Section
  ├─ Source Stack
  └─ Change Summary
```

Gaia toont niet alle 800 regels. Alleen:

- huidige sectie,
- voortgang,
- keuzes,
- eventuele vragen of blokkades.

## 20.5 Stap 5: resultaat

Gaia levert:

- Uitgebreide constitution-laag.
- UI/UX-visie.
- Information architecture.
- Component library.
- Component DNA.
- Design language.
- Assistant character.
- Experience Engine.
- End-to-end voorbeeldflow.
- Roadmap-uitbreiding.
- Bronnen.

## 20.6 Stap 6: reflectie na afloop

Na de taak schrijft Gaia intern:

```text
Reflection

What worked:
- Bestaande documentstructuur kon worden uitgebreid zonder code.
- Voorbeeldtekst gaf duidelijke richting voor Gaia Constitution.
- UI/UX werd concreet via spaces, componenten en flows.

Memory candidate:
- Gebruiker wil Gaia positioneren als living AI companion OS.
- Gebruiker houdt van constitution-style productdocumentatie.

Curiosity candidate:
- Maak later een aparte Gaia Component Library Spec.
- Maak later een Claude implementation prompt uit deze constitution.
```

## 21. Roadmap-uitbreiding met UI/UX

### Fase 10 — Gaia Constitution v1.0

**Doel:** een single source of truth maken.

**Deliverables:**

- Mission.
- Philosophy.
- Architecture.
- Intelligence rules.
- Memory rules.
- UI rules.
- Safety rules.
- Development standards.

### Fase 11 — UI/UX Foundation

**Doel:** bepalen hoe Gaia voelt en werkt voordat er schermen gebouwd worden.

**Deliverables:**

- UI/UX-visie.
- Information architecture.
- Space model.
- Navigatieprincipes.
- Interaction principles.
- Accessibility principles.

### Fase 12 — Design Language

**Doel:** visuele consistentie vastleggen.

**Deliverables:**

- Kleurstates.
- Typografie.
- Spacing.
- Materiaalgebruik.
- Motion language.
- Dark/light mode-principes.

### Fase 13 — Component Library Spec

**Doel:** alle UI bouwen uit vaste componenten.

**Deliverables:**

- Componentlijst.
- Component DNA.
- State model.
- Accessibility requirements.
- Missing Component Protocol.

### Fase 14 — Experience Engine

**Doel:** meten of interacties nuttig, duidelijk en prettig zijn.

**Deliverables:**

- Experience Score.
- UI-frictiemetrics.
- Feedbackregels.
- Curiosity-koppeling.

### Fase 15 — Prototype zonder code

**Doel:** eerst de ervaring valideren.

**Deliverables:**

- Wireframes.
- Belangrijkste flows.
- Voorbeeldschermen.
- Componentgedrag.
- Motion-notities.

### Fase 16 — Bouwbare specificatie

**Doel:** het document vertalen naar implementatie-instructies.

**Deliverables:**

- Claude implementation prompt.
- Data contracts.
- API boundaries.
- Frontend component contracts.
- Eerste technische backlog.

## 22. Herbruikbare GitHub-bouwblokken

Doel van deze sectie: Gaia moet niet alles zelf bouwen. Voor elk onderdeel zoekt de Tool Builder eerst naar bestaande open-source projecten, MCP-servers, SDKs of self-hosted tools. Pas als hergebruik te riskant, te beperkt of te duur is, wordt iets zelf gebouwd.

**Vuistregel:**

```text
Eerst hergebruiken
  ↓
Dan aanpassen
  ↓
Dan wrapper/MCP maken
  ↓
Pas als laatste zelf volledig bouwen
```

## 22.1 Evaluatieregel voor GitHub-projecten

Elke repo krijgt vóór installatie een korte beoordeling.

| Criteria | Vraag |
|---|---|
| Onderhoud | Is de repo recent bijgewerkt en niet gearchiveerd? |
| Adoptie | Zijn er gebruikers, issues, releases, forks of documentatie? |
| Veiligheid | Welke permissies, tokens, scopes en lokale toegang vraagt het project? |
| Reproduceerbaarheid | Is de installatie duidelijk en testbaar in een sandbox? |
| Fit | Lost het echt een Gaia-probleem op, of is het alleen interessant? |
| Onderhoudslast | Wordt Gaia afhankelijk van fragiele scraping, private APIs of veel services? |
| Exit | Kan het later makkelijk vervangen worden? |

**Defaultactie:**

- Actieve, bekende projecten mogen naar de evaluatie-backlog.
- Kleine of experimentele projecten mogen alleen in sandbox.
- Gearchiveerde projecten worden inspiratie, niet basisarchitectuur.
- Tools met bank, betaling, trading, e-mail, agenda, tickets of serverbeheer krijgen extra approval.

## 22.2 Aanbevolen startstack

Dit is de meest logische eerste combinatie als Gaia bouwbaar moet worden zonder alles zelf te schrijven.

| Laag | Startkeuze | Waarom |
|---|---|---|
| Agent runtime | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) of [LangGraph](https://github.com/langchain-ai/langgraph) | Duidelijke orchestration voor tools, state en multi-agent taken |
| Workflow automation | [n8n](https://github.com/n8n-io/n8n) of [Activepieces](https://github.com/activepieces/activepieces) | Taken, triggers, approvals en koppelingen zonder alles te coderen |
| MCP-basis | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers), [FastMCP](https://github.com/PrefectHQ/fastmcp), [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | Herbruikbare servers en snelle eigen wrappers |
| Browser/web | [Playwright MCP](https://github.com/microsoft/playwright-mcp), [Browser Use](https://github.com/browser-use/browser-use), [Firecrawl](https://github.com/firecrawl/firecrawl), [Apify MCP](https://github.com/apify/apify-mcp-server) | Websites gebruiken, webresearch doen en data ophalen |
| Memory/graph | [Mem0](https://github.com/mem0ai/mem0), [Graphiti](https://github.com/getzep/graphiti), [Cognee](https://github.com/topoteretes/cognee) | Persoonlijk geheugen, contextgraph en retrieval niet zelf vanaf nul bouwen |
| Model routing | [LiteLLM](https://github.com/BerriAI/litellm), [Ollama](https://github.com/ollama/ollama), [vLLM](https://github.com/vllm-project/vllm), [llama.cpp](https://github.com/ggml-org/llama.cpp) | Lokaal/extern modelgebruik sturen op kosten, snelheid en hardware |
| Observability | [Langfuse](https://github.com/langfuse/langfuse) | Traces, evaluaties, prompts, kosten en kwaliteit meten |
| Serverbeheer | [Uptime Kuma](https://github.com/louislam/uptime-kuma), [Portainer](https://github.com/portainer/portainer), [Netdata](https://github.com/netdata/netdata), [Ansible](https://github.com/ansible/ansible) | Monitoring en beheer zonder custom dashboard vanaf nul |

## 22.3 Projectcatalogus per Gaia-onderdeel

| Gaia-onderdeel | Projecten om te evalueren | Gebruik in Gaia | Let op |
|---|---|---|---|
| Agent orchestration | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python), [LangGraph](https://github.com/langchain-ai/langgraph), [CrewAI](https://github.com/crewAIInc/crewAI), [AutoGen](https://github.com/microsoft/autogen), [Agno](https://github.com/agno-agi/agno), [Mastra](https://github.com/mastra-ai/mastra), [Semantic Kernel](https://github.com/microsoft/semantic-kernel), [VoltAgent](https://github.com/VoltAgent/voltagent) | Personal Agent, Research Agent en gespecialiseerde rollen bouwen | Kies één primaire runtime; meerdere tegelijk maakt debugging moeilijk |
| Coding/long-running work | [OpenHands](https://github.com/OpenHands/OpenHands), [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk), [OpenCode](https://github.com/opencode-ai/opencode) | Grote code- en toolbouwtaken door laten werken | Alleen in repos/sandboxes met duidelijke rollback |
| Agent command center | [Maestro](https://github.com/RunMaestro/Maestro) | Meerdere agents/projecten zichtbaar organiseren | Evalueren als UI/operational laag, niet als kernbrein |
| MCP ecosysteem | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers), [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers), [FastMCP](https://github.com/PrefectHQ/fastmcp) | Nieuwe tools sneller koppelen | Elke MCP-server krijgt permissiemanifest |
| Memory en knowledge graph | [Mem0](https://github.com/mem0ai/mem0), [Graphiti](https://github.com/getzep/graphiti), [Cognee](https://github.com/topoteretes/cognee), [LlamaIndex](https://github.com/run-llama/llama_index), [GraphRAG](https://github.com/microsoft/graphrag), [Neo4j MCP](https://github.com/neo4j-contrib/mcp-neo4j), [OpenViking](https://github.com/volcengine/OpenViking) | Long-term memory, bronprovenance, contextgraph, documentretrieval | Begin klein; memory is nutteloos als opschoning en confidence ontbreken |
| Zelfverbetering en observability | [Langfuse](https://github.com/langfuse/langfuse), [VoltAgent](https://github.com/VoltAgent/voltagent) | Traces, toolkwaliteit, prompts, evals, feedbackloops | Geen persoonlijke secrets in logs opslaan |
| Workflow automation | [n8n](https://github.com/n8n-io/n8n), [Activepieces](https://github.com/activepieces/activepieces), [Flowise](https://github.com/FlowiseAI/Flowise), [Dify](https://github.com/langgenius/dify), [Home Assistant](https://github.com/home-assistant/core) | Night Queue, routine-automations, notificaties, approvals | Workflowtools mogen geen approvalregels omzeilen |
| Browser en webresearch | [Playwright MCP](https://github.com/microsoft/playwright-mcp), [Browser Use](https://github.com/browser-use/browser-use), [Firecrawl](https://github.com/firecrawl/firecrawl), [Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server), [Apify MCP](https://github.com/apify/apify-mcp-server) | Websites lezen, research doen, formulieren voorbereiden, data verzamelen | Geen captcha-bypass of agressieve scraping |
| Agenda, mail en planner | [Google Workspace MCP](https://github.com/taylorwilsdon/google_workspace_mcp), [Calendar MCP](https://github.com/MarimerLLC/calendar-mcp), [email-mcp](https://github.com/codefuturist/email-mcp), [Google MCP](https://github.com/google/mcp) | Gmail, Calendar, Drive, Tasks, contacten en planning | Draft/read-first; verzenden en schrijven alleen met approval |
| Magister/school | [unofficial-magister-mcp](https://github.com/israelroldan/unofficial-magister-mcp), [magister-tool](https://github.com/nlitsme/magister-tool) | Schoolagenda en rooster ophalen | Onofficiële tools: sandbox, beperkte login, goed testen |
| WK en sportkalenders | [world-cup-ics](https://github.com/thatbritguy/world-cup-ics), [openfootball/worldcup.json](https://github.com/openfootball/worldcup.json), [openfootball/football.json](https://github.com/openfootball/football.json) | WK-wedstrijden en andere voetbaldata in agenda zetten | Bronnen vergelijken met officiële tijden voordat events worden geschreven |
| Shopper/deals | [Apify MCP](https://github.com/apify/apify-mcp-server), [Vinted Scraper](https://github.com/Giglium/vinted_scraper), [marktplaats-py](https://github.com/jensjeflensje/marktplaats-py), [marktplaats-scraper](https://github.com/chadsr/marktplaats-scraper), [shoppingscraper-cli](https://github.com/ShoppingResult/shoppingscraper-cli), [BuyWhere MCP](https://github.com/buywhere/buywhere-mcp), [mcp-ticketer](https://github.com/bobmatnyc/mcp-ticketer) | Prijsalerts, productvergelijking, dealshortlists, conceptberichten | Geen automatisch kopen/bieden; geen blokkades omzeilen |
| Geld, marktdata en investeren | [bank-mcp](https://github.com/elcukro/bank-mcp), [OpenBB](https://github.com/OpenBB-finance/OpenBB), [Financial Datasets MCP](https://github.com/financial-datasets/mcp-server), [PayPal MCP Server](https://github.com/paypal/paypal-mcp-server), [PayPal Agent Toolkit](https://github.com/paypal/agent-toolkit), [Freqtrade](https://github.com/freqtrade/freqtrade) | Read-only bankoverzicht, marktdata, onderzoek, sandboxbetalingen | Geen financieel advies of trades zonder menselijke beslissing |
| Server manager | [Uptime Kuma](https://github.com/louislam/uptime-kuma), [Portainer](https://github.com/portainer/portainer), [Netdata](https://github.com/netdata/netdata), [Ansible](https://github.com/ansible/ansible), [Renovate](https://github.com/renovatebot/renovate) | Uptime, containers, metrics, configbeheer, dependency updates | Wijzigingen aan productiecontainers alleen na approval |
| Container auto-update inspiratie | [Watchtower](https://github.com/containrrr/watchtower) | Ideeën voor updatebeleid | Repo is gearchiveerd; niet als nieuwe basis gebruiken |
| Model serving en GPU-routing | [LiteLLM](https://github.com/BerriAI/litellm), [Ollama](https://github.com/ollama/ollama), [vLLM](https://github.com/vllm-project/vllm), [llama.cpp](https://github.com/ggml-org/llama.cpp), [LocalAI](https://github.com/mudler/LocalAI), [Open WebUI](https://github.com/open-webui/open-webui), [Harbor](https://github.com/av/harbor), [Colibri](https://github.com/JustVugg/colibri) | Lokaal model draaien, externe modellen routeren, VRAM beperken, UI voor modellen | Colibri is interessant/experimenteel; eerst testen met kleine taken |
| Persoonlijke AI als referentie | [Khoj](https://github.com/khoj-ai/khoj), [Open WebUI](https://github.com/open-webui/open-webui), [Dify](https://github.com/langgenius/dify) | Inspiratie of deels herbruikbare app-laag | Niet automatisch Gaia vervangen; alleen onderdelen lenen |

## 22.4 Projecten uit de Notities-bronnen

Deze bronnen stonden al in de Apple Notes-notitie en blijven in de evaluatie-backlog.

| Bron | Mogelijke rol in Gaia | Status |
|---|---|---|
| [S.I.R.I.U.S. discussion](https://github.com/Devjosef/S.I.R.I.U.S./discussions/1) | Inspiratie voor self-learning en toolontwikkeling | Lezen en ideeën extraheren |
| [OpenViking](https://github.com/volcengine/OpenViking) | Contextdatabase voor agents | Serieus evalueren naast Mem0/Graphiti/Cognee |
| [VoltAgent](https://github.com/VoltAgent/voltagent) | TypeScript agent framework met memory, tools, MCP en observability | Evalueren als TS-stack |
| [Bytebot](https://github.com/bytebot-ai/bytebot) | Self-hosted desktop/computer-use agent | Gearchiveerd; alleen inspiratie |
| [bank-mcp](https://github.com/elcukro/bank-mcp) | Read-only banktoegang via open banking providers | Alleen read-only en met sterke scopes |
| [mcp-market-data-server](https://github.com/fintools-ai/mcp-market-data-server) | Marktdata voor Manager Agent | Evalueren naast OpenBB/Financial Datasets |
| [mcp-ticketer](https://github.com/bobmatnyc/mcp-ticketer) | Ticket/dealonderzoek | Alleen monitoren en concepten; geen autobuy |
| [PayPal MCP Server](https://github.com/paypal/paypal-mcp-server) | PayPal-integratie | Eerst sandbox; betalingen altijd approval |
| [mcp-supersubagents](https://github.com/yigitkonur/mcp-supersubagents) | Subagent orchestration | Evalueren in sandbox |
| [chaterm](https://github.com/chaterm/chaterm) | Terminal/chat workflow | Evalueren als developer interface |
| [openai-oauth](https://github.com/EvanZhouDev/openai-oauth) | OAuth/reference voor OpenAI-loginflows | Alleen als referentie, security review vereist |
| [OpenCode](https://github.com/opencode-ai/opencode) | Open-source coding agent | Evalueren voor code/agentic work |
| [Colibri](https://github.com/JustVugg/colibri) | Grote MoE-modellen lokaal met weinig geheugen verkennen | Experimenteel; testen zonder kritieke afhankelijkheid |

## 22.5 Eerste technische backlog uit de GitHub-scan

| Prioriteit | Taak | Output |
|---|---|---|
| P0 | Kies primaire agent runtime: OpenAI Agents SDK, LangGraph of VoltAgent | Keuzedocument met trade-offs |
| P0 | Maak permissiemodel voor MCP Hub | Read/write scopes, approvalregels, auditlog |
| P0 | Zet observability op met Langfuse of vergelijkbaar | Traceerbare toolruns en kosten |
| P1 | Test Memory Engine met Mem0, Graphiti, Cognee en OpenViking | Prototype met dezelfde dataset en evaluatievragen |
| P1 | Test browserlaag met Playwright MCP, Browser Use, Firecrawl en Apify | Betrouwbaarheid per taaktype |
| P1 | Maak Planner proof-of-concept met Google Workspace MCP en WK-ICS | Agenda-preview zonder direct schrijven |
| P1 | Maak Server Manager read-only dashboard met Uptime Kuma/Portainer/Netdata | Wekelijks rapport zonder wijzigingen |
| P2 | Maak Shopper proof-of-concept voor Vinted/Marktplaats alerts | Shortlist + conceptbericht, geen aankoop |
| P2 | Maak Model Scheduler prototype met LiteLLM + Ollama/vLLM | Kosten/snelheid/privacy routing |
| P2 | Maak finance sandbox met OpenBB, bank-mcp en PayPal sandbox | Read-only analyse en betaal-preview |

## 22.6 Aanvullende bronnen uit tweede zoekronde

Deze bronnen zijn extra kandidaten die Gaia later kan evalueren. Ze zijn bewust per probleemgebied gegroepeerd, zodat de Tool Builder ze niet allemaal tegelijk hoeft te proberen.

| Probleemgebied | Extra projecten | Waarom interessant voor Gaia | Eerste beoordeling |
|---|---|---|---|
| Productie-agent frameworks | [Pydantic AI](https://github.com/pydantic/pydantic-ai), [Letta](https://github.com/letta-ai/letta), [CAMEL](https://github.com/camel-ai/camel), [CAMEL OWL](https://github.com/camel-ai/OWL), [mcp-agent](https://github.com/lastmile-ai/mcp-agent), [Inngest AgentKit](https://github.com/inngest/agent-kit) | Extra opties voor stateful agents, typed Python agents, multi-agent samenwerking en MCP-native agents | Evalueren naast OpenAI Agents SDK, LangGraph en VoltAgent |
| Durable execution | [Temporal](https://github.com/temporalio/temporal), [Hatchet](https://github.com/hatchet-dev/hatchet), [Inngest](https://github.com/inngest/inngest), [Windmill](https://github.com/windmill-labs/windmill), [Prefect](https://github.com/PrefectHQ/prefect) | Lange taken kunnen pauzeren, herstellen na fouten, retryen en wachten op menselijke approval | Sterke kandidaat voor Night Queue en Research Agent |
| MCP discovery en beheer | [GitHub MCP Server](https://github.com/github/github-mcp-server), [Docker MCP Registry](https://github.com/docker/mcp-registry), [Docker MCP Gateway](https://github.com/docker/mcp-gateway), [Desktop Commander MCP](https://github.com/wonderwhy-er/DesktopCommanderMCP), [OpenAI Agents MCP extension](https://github.com/lastmile-ai/openai-agents-mcp), [mcp-eval](https://github.com/lastmile-ai/mcp-eval) | MCP-servers vinden, lokaal veiliger draaien, GitHub koppelen, MCP-tools testen | Desktop/terminal MCP alleen met strakke sandbox en approval |
| Code execution sandbox | [E2B](https://github.com/e2b-dev/e2b), [Daytona](https://github.com/daytonaio/daytona), [Pydantic Monty](https://github.com/pydantic/monty), [Open Interpreter](https://github.com/openinterpreter/openinterpreter) | AI-code draaien zonder je echte systeem direct bloot te stellen | Cruciaal voordat Gaia zelf code of scripts mag uitvoeren |
| Document-ingestie | [MarkItDown](https://github.com/microsoft/markitdown), [Docling](https://github.com/docling-project/docling), [Unstructured](https://github.com/Unstructured-IO/unstructured), [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | PDFs, Office-bestanden, afbeeldingen en notities klaarmaken voor RAG/memory | Goed voor Apple Notes export, schooldocs, handleidingen en serverdocs |
| Vector/RAG opslag | [Qdrant](https://github.com/qdrant/qdrant), [Chroma](https://github.com/chroma-core/chroma), [Weaviate](https://github.com/weaviate/weaviate), [Milvus](https://github.com/milvus-io/milvus), [LanceDB](https://github.com/lancedb/lancedb), [pgvector](https://github.com/pgvector/pgvector) | Semantisch zoeken, long-term memory en documentretrieval | Begin met één simpele store; later pas vergelijken |
| Model serving extra | [SGLang](https://github.com/sgl-project/sglang), [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM), [LMDeploy](https://github.com/InternLM/lmdeploy), [ExLlamaV2](https://github.com/turboderp-org/exllamav2) | Snellere lokale of GPU-inference dan alleen Ollama/vLLM in bepaalde situaties | Alleen nodig als lokale modellen echt bottleneck worden |
| Voice assistant | [whisper.cpp](https://github.com/ggml-org/whisper.cpp), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Piper](https://github.com/OHF-voice/piper1-gpl), [openWakeWord](https://github.com/dscripka/openWakeWord), [Open Interpreter 01](https://github.com/openinterpreter/01) | Spraak naar tekst, lokale TTS, wake word en desktop/voice control | Later toevoegen; eerst tekstinterface betrouwbaar maken |
| Privacy en security | [Infisical](https://github.com/Infisical/infisical), [Vault](https://github.com/hashicorp/vault), [SOPS](https://github.com/getsops/sops), [Gitleaks](https://github.com/gitleaks/gitleaks), [TruffleHog](https://github.com/trufflesecurity/trufflehog), [Open Policy Agent](https://github.com/open-policy-agent/opa), [Presidio](https://github.com/data-privacy-stack/presidio) | Secrets bewaren, tokens scannen, PII maskeren en policies afdwingen | P0 zodra Gaia echte accounts/tokens krijgt |
| Eval en observability | [Promptfoo](https://github.com/promptfoo/promptfoo), [Phoenix](https://github.com/Arize-ai/phoenix), [OpenLIT](https://github.com/openlit/openlit), [Helicone](https://github.com/Helicone/helicone), [Pydantic Logfire](https://github.com/pydantic/logfire) | Prompts testen, agents evalueren, traces bekijken, regressies vinden | Combineer met Langfuse of vergelijk als alternatief |
| Self-hosting dashboard | [Beszel](https://github.com/henrygd/beszel), [Komodo](https://github.com/moghtech/komodo), [Dockge](https://github.com/louislam/dockge), [Homepage](https://github.com/gethomepage/homepage), [Glance](https://github.com/glanceapp/glance), [Traefik](https://github.com/traefik/traefik), [Caddy](https://github.com/caddyserver/caddy), [Authelia](https://github.com/authelia/authelia), [NetBird](https://github.com/netbirdio/netbird), [CrowdSec](https://github.com/crowdsecurity/crowdsec) | Serverstatus, containers, reverse proxy, login en basisbeveiliging | Goed voor Server Manager Agent en homelabbeheer |
| Persoonlijke interface | [LibreChat](https://github.com/danny-avila/LibreChat), [Lobe Chat](https://github.com/lobehub/lobe-chat), [big-AGI](https://github.com/enricoros/big-AGI), [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | Bestaande UI-ideeën voor multi-model chat, agents, files, memory en MCP | Alleen lenen/inspireren; Gaia blijft eigen productvisie houden |
| Planner, taken en geld | [Vikunja](https://github.com/go-vikunja/vikunja), [Cal.diy](https://github.com/calcom/cal.diy), [Actual Budget](https://github.com/actualbudget/actual), [Firefly III](https://github.com/firefly-iii/firefly-iii), [Beancount](https://github.com/beancount/beancount) | Taken, scheduling, persoonlijke begroting en scriptbare boekhouding | Finance blijft read-only tenzij de gebruiker expliciet tekent |
| Integratieplatformen | [Composio](https://github.com/ComposioHQ/composio), [Pipedream](https://github.com/PipedreamHQ/pipedream) | Veel externe apps koppelen zonder elke API zelf te bouwen | Alleen gebruiken met duidelijke OAuth-scopes |

## 22.7 Nieuwe backlog-items uit tweede bronronde

| Prioriteit | Taak | Output |
|---|---|---|
| P0 | Ontwerp sandboxbeleid voor code, browser en terminal | Wanneer E2B/Daytona/Monty/lokale container gebruikt wordt |
| P0 | Ontwerp secrets- en tokenbeheer | Infisical/Vault/SOPS-keuze, plus Gitleaks/TruffleHog scanregels |
| P1 | Vergelijk durable execution opties | Temporal vs Hatchet vs Inngest vs Windmill voor Night Queue |
| P1 | Maak document-ingestie prototype | Apple Notes/export, PDF, DOCX en Markdown via MarkItDown/Docling |
| P1 | Maak privacyfilter voor memory | Presidio/PII-detectie voordat gesprekken permanent worden opgeslagen |
| P2 | Test voice assistant stack | whisper.cpp/faster-whisper + Piper + openWakeWord |
| P2 | Test self-hosting dashboard voor Gaia servers | Beszel/Komodo/Dockge/Homepage met read-only statuspaneel |
| P2 | Test eval-suite | Promptfoo/mcp-eval/Phoenix/OpenLIT naast Langfuse |

## 23. Aanbevolen bronnen

- Model Context Protocol-documentatie: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP-specificatie: https://modelcontextprotocol.io/specification/2025-03-26
- OpenAI Agents SDK-documentatie: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents SDK Python-docs: https://openai.github.io/openai-agents-python/
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- NIST AI RMF 1.0 PDF: https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf
- Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines
- Apple Human Interface Guidelines - Motion: https://developer.apple.com/design/human-interface-guidelines/motion
- Material Design 3 - Motion: https://m3.material.io/styles/motion/overview/how-it-works
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
- WAI-ARIA Authoring Practices Guide: https://www.w3.org/WAI/ARIA/apg/
- GitHub MCP server catalogus: https://github.com/modelcontextprotocol/servers
- Awesome MCP servers: https://github.com/punkpeye/awesome-mcp-servers
- OpenAI Agents SDK repo: https://github.com/openai/openai-agents-python
- LangGraph repo: https://github.com/langchain-ai/langgraph
- Playwright MCP repo: https://github.com/microsoft/playwright-mcp
- Browser Use repo: https://github.com/browser-use/browser-use
- Mem0 repo: https://github.com/mem0ai/mem0
- Graphiti repo: https://github.com/getzep/graphiti
- Cognee repo: https://github.com/topoteretes/cognee
- LiteLLM repo: https://github.com/BerriAI/litellm
- Ollama repo: https://github.com/ollama/ollama
- vLLM repo: https://github.com/vllm-project/vllm
- n8n repo: https://github.com/n8n-io/n8n
- Activepieces repo: https://github.com/activepieces/activepieces
- Langfuse repo: https://github.com/langfuse/langfuse
- OpenViking repo: https://github.com/volcengine/OpenViking
- VoltAgent repo: https://github.com/VoltAgent/voltagent
- OpenCode repo: https://github.com/opencode-ai/opencode
- Colibri repo: https://github.com/JustVugg/colibri
- World Cup ICS repo: https://github.com/thatbritguy/world-cup-ics
- openfootball worldcup.json: https://github.com/openfootball/worldcup.json
- Pydantic AI repo: https://github.com/pydantic/pydantic-ai
- Letta repo: https://github.com/letta-ai/letta
- CAMEL repo: https://github.com/camel-ai/camel
- mcp-agent repo: https://github.com/lastmile-ai/mcp-agent
- Temporal repo: https://github.com/temporalio/temporal
- Hatchet repo: https://github.com/hatchet-dev/hatchet
- Windmill repo: https://github.com/windmill-labs/windmill
- Docker MCP Registry: https://github.com/docker/mcp-registry
- GitHub MCP Server: https://github.com/github/github-mcp-server
- E2B repo: https://github.com/e2b-dev/e2b
- Daytona repo: https://github.com/daytonaio/daytona
- Pydantic Monty repo: https://github.com/pydantic/monty
- MarkItDown repo: https://github.com/microsoft/markitdown
- Docling repo: https://github.com/docling-project/docling
- Qdrant repo: https://github.com/qdrant/qdrant
- Weaviate repo: https://github.com/weaviate/weaviate
- Chroma repo: https://github.com/chroma-core/chroma
- LanceDB repo: https://github.com/lancedb/lancedb
- SGLang repo: https://github.com/sgl-project/sglang
- TensorRT-LLM repo: https://github.com/NVIDIA/TensorRT-LLM
- whisper.cpp repo: https://github.com/ggml-org/whisper.cpp
- faster-whisper repo: https://github.com/SYSTRAN/faster-whisper
- Piper repo: https://github.com/OHF-voice/piper1-gpl
- openWakeWord repo: https://github.com/dscripka/openWakeWord
- Infisical repo: https://github.com/Infisical/infisical
- Open Policy Agent repo: https://github.com/open-policy-agent/opa
- Presidio repo: https://github.com/data-privacy-stack/presidio
- Promptfoo repo: https://github.com/promptfoo/promptfoo
- Phoenix repo: https://github.com/Arize-ai/phoenix
- OpenLIT repo: https://github.com/openlit/openlit
- Helicone repo: https://github.com/Helicone/helicone
- Beszel repo: https://github.com/henrygd/beszel
- Komodo repo: https://github.com/moghtech/komodo
- Dockge repo: https://github.com/louislam/dockge
- LibreChat repo: https://github.com/danny-avila/LibreChat
- Lobe Chat repo: https://github.com/lobehub/lobe-chat
- Actual Budget repo: https://github.com/actualbudget/actual
- Firefly III repo: https://github.com/firefly-iii/firefly-iii
- Vikunja repo: https://github.com/go-vikunja/vikunja
- Cal.diy repo: https://github.com/calcom/cal.diy

## 24. Definitieve positionering

De assistent is geen simpele chatbot en ook geen volledig autonome robot. Het is een persoonlijk besturingssysteem voor kennis, taken, research, UI-compositie en zelfverbetering.

De unieke kern zit in de combinatie van:

- **Memory Engine** voor persoonlijke continuïteit.
- **Knowledge Graph** voor relaties en context.
- **Value Engine** voor prioriteit en veiligheid.
- **Opportunity Engine** voor externe kansen.
- **Curiosity Engine** voor interne zelfverbetering.
- **Research Agent** voor diep werk.
- **Night Improvement System** voor continue groei zonder de gebruiker overdag te vertragen.
- **UI Composition Engine** voor contextuele interfaces uit vaste componenten.
- **Component DNA** voor uitbreidbare, consistente UI-bouwblokken.
- **Gaia Genome** voor langzaam aanpasbaar gedrag.
- **Experience Engine** voor het meten van bruikbaarheid, vertrouwen en interactiekwaliteit.
- **Evolution Journal** voor zichtbare groei over weken en maanden.

Hierdoor ontstaat een assistent die overdag snel is, bij complexe taken diep kan werken, interfaces contextueel kan samenstellen en 's nachts slimmer wordt.
