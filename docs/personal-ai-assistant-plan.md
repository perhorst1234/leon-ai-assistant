# Personal AI Assistant — uitgewerkt conceptplan

## 1. Productvisie

Het doel is een persoonlijke AI-assistent die niet alleen reageert op vragen, maar zichzelf structureel verbetert. Het systeem bestaat uit een snelle dagelijkse assistent, een zware researchlaag voor complexe taken en een nachtelijke verbetercyclus die leert van gesprekken, tools, fouten, kansen en terugkerende patronen.

De assistent moet drie dingen tegelijk kunnen:

1. **Direct helpen** bij eenvoudige vragen en kleine taken.
2. **Diep werken** aan grote opdrachten via gespecialiseerde agents en tools.
3. **Zichzelf verbeteren** door kansen in de buitenwereld en patronen in het eigen gedrag te analyseren.

Belangrijk uitgangspunt: de assistent voert niet zomaar alles uit. Nieuwe ideeën, tools, MCP-servers, automatiseringen en verbeteringen gaan eerst door een waardefilter en waar nodig door menselijke goedkeuring.

## 2. Hoofdarchitectuur

```text
                           Chat / Interface
                                  │
                         Personal Agent
                                  │
          ┌──────────────┬────────┴────────┬──────────────┐
          │              │                 │              │
    Memory Engine   Knowledge Graph   Task Manager   Value Engine
          │              │                 │              │
          └──────────────┴────────┬────────┴──────────────┘
                                  │
                         Decision Layer
                                  │
                  ┌───────────────┴───────────────┐
                  │                               │
             Live Execution                 Research Agent
                  │                               │
                  │           ┌───────────────────┼───────────────────┐
                  │           │                   │                   │
                  │        Planner            Workers              Tools
                  │           │                   │                   │
                  │     Subtaken          Browser / Code /      Databases /
                  │                       Python / Search       Files / APIs
                  │                               │
                  └────────────── Resultaat + bronnen ────────────────┘
                                  │
                   Night Improvement System
                                  │
        ┌──────────────┬──────────┴──────────┬──────────────┐
        │              │                     │              │
 Opportunity Engine  Curiosity Engine   Feedback Engine  MCP Hub
        │              │                     │              │
        └──────────────┴──────────┬──────────┴──────────────┘
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

## 12. Roadmap zonder coderen

## Fase 1 — Hersenen definiëren

**Doel:** alle componenten en verantwoordelijkheden scherp krijgen.

**Deliverables:**

- Componentkaart.
- Verantwoordelijkheidsmatrix.
- Datamodel op hoofdlijnen.
- Beslisregels voor Live vs Research.
- Eerste Value Engine-scorekaart.

## Fase 2 — Beslislaag ontwerpen

**Doel:** voorkomen dat zware agents onnodig worden gebruikt.

**Deliverables:**

- Intentietaxonomie.
- Complexiteitsscore.
- Risicomatrix.
- Routebeslisboom.
- Escalatieregels.

## Fase 3 — Memory en Knowledge Graph ontwerp

**Doel:** context betrouwbaar organiseren.

**Deliverables:**

- Memorytypen.
- Retentiebeleid.
- Graph-entiteiten en relaties.
- Confidence- en expiryregels.
- Privacyregels.

## Fase 4 — Night Improvement System ontwerp

**Doel:** automatische nachtelijke verwerking specificeren.

**Deliverables:**

- Night Cycle schema.
- Ochtendrapport-template.
- Task Queue-regels.
- Feedbackmetingen.
- Approvalbeleid.

## Fase 5 — Opportunity Engine ontwerp

**Doel:** externe kansen vinden zonder willekeur.

**Deliverables:**

- Bronlijst.
- Scanfrequenties.
- Relevantiecriteria.
- Source scoring.
- Opportunity-template.

## Fase 6 — Curiosity Engine ontwerp

**Doel:** interne frictie en herhaling omzetten in verbeterideeën.

**Deliverables:**

- Logsignalen.
- Frictiemetrics.
- Patroondetectieregels.
- CuriosityInsight-template.
- Experiment- en evaluatieregels.

## Fase 7 — Value Engine verfijnen

**Doel:** alle ideeën, taken en tools objectief prioriteren.

**Deliverables:**

- Definitieve scoreformule.
- Risicodrempels.
- Kostenmodel.
- ROI-model.
- Besluitregels per scoreband.

## Fase 8 — Research Agent specificeren

**Doel:** diepe taken zelfstandig laten plannen en uitvoeren.

**Deliverables:**

- Planner-specificatie.
- Workerrollen.
- Rapportformat.
- Bronnencontrole.
- Stop- en approvalcriteria.

## Fase 9 — Governance en evaluatie

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

Pas daarna is het verstandig om te coderen.

## 14. Aanbevolen bronnen

- Model Context Protocol-documentatie: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP-specificatie: https://modelcontextprotocol.io/specification/2025-03-26
- OpenAI Agents SDK-documentatie: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents SDK Python-docs: https://openai.github.io/openai-agents-python/
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- NIST AI RMF 1.0 PDF: https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf

## 15. Definitieve positionering

De assistent is geen simpele chatbot en ook geen volledig autonome robot. Het is een persoonlijk besturingssysteem voor kennis, taken, research en zelfverbetering.

De unieke kern zit in de combinatie van:

- **Memory Engine** voor persoonlijke continuïteit.
- **Knowledge Graph** voor relaties en context.
- **Value Engine** voor prioriteit en veiligheid.
- **Opportunity Engine** voor externe kansen.
- **Curiosity Engine** voor interne zelfverbetering.
- **Research Agent** voor diep werk.
- **Night Improvement System** voor continue groei zonder de gebruiker overdag te vertragen.

Hierdoor ontstaat een assistent die overdag snel is, bij complexe taken diep kan werken en 's nachts slimmer wordt.
