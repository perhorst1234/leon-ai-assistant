# PRD: Leon Personal AI Environment

## 1. Productdefinitie

**Productnaam:** Leon  
**Primaire gebruiker:** alleen de eigenaar/gebruiker van dit systeem  
**Producttype:** lokale, persoonlijke AI-omgeving met autonome agents, memory graph, tool-integraties en een levende premium interface.

Leon is geen standaard chatbot en geen SaaS-dashboard. Leon moet voelen als een rustige, intelligente omgeving die meedenkt, leert, taken uitvoert, relevante kennis terugvindt en zichzelf gecontroleerd verbetert.

De bestaande control-plane blijft de technische/governance-laag. De uiteindelijke productervaring wordt Leon: een AI-native canvas met dynamische componenten, bottom dock, zichtbaar digitaal personage en adaptive transparency.

## 2. Productgevoel

Leon moet visueel en interactief aanvoelen als:

- 40% AI-native
- 40% Arc Browser
- 20% Apple

De UI is premium, rustig, modern en menselijk. Niet gameachtig, niet overdreven futuristisch, niet als een klassiek dashboard.

Belangrijke stijlregels:

- donkere zachte achtergronden
- subtiele gradients en noise
- glassmorphism-panelen
- afgeronde hoeken
- zachte blur, glow en schaduw
- veel witruimte
- weinig zichtbare randen
- één dynamische accentkleur

Statuskleuren:

- blauw: idle/rust
- paars: thinking
- cyaan: acting/executing
- amber: attention/review
- rood: echte fout of gevaar

## 3. Strategisch Doel

Leon moet de persoonlijke OS-laag worden voor kennis, taken, onderzoek, automatisering en zelfverbetering.

V1 focust niet op zo veel mogelijk tools, maar op:

1. brede memory/knowledge graph
2. relevante kennis sneller vinden dan handmatig zoeken
3. autonomous night queue binnen risicoklassen
4. morning brief met acties, ontdekkingen en verbeteringen
5. eerste levende Leon UI met canvas, dock en character

## 4. Huidige Basis

Er bestaat al een foundation/control-plane met:

- lokale dashboardserver op `127.0.0.1:8765`
- governance, auditlog en approval-systemen
- modelrouting foundation
- agent assignment proposals
- mock agent-runs
- OpenAI provider dry-run
- env/API-key intake zonder raw secrets tonen
- memory/knowledge graph MVP
- UI-composition foundation
- missing component protocol
- tests en validatie rond routing, audit, secrets en scripts

Deze PRD bouwt hierop voort. De backend mag efficiënter of beter worden ontworpen dan het originele plan, zolang de productervaring en visuele richting van Leon intact blijven.

## 5. V1 Release Scope

V1 heet: **Leon Night Memory Release**

V1 bevat:

- autonomous night queue
- morning brief
- brede persoonlijke memory/knowledge graph
- lokale en externe data-ingestie
- mail/calendar/browser/tool-integraties binnen risicoklassen
- eerste levende canvas UI
- bottom dock
- Leon character
- adaptive transparency
- kostenwaarschuwingen bij dure acties
- rollback/diff/log/back-up beleid per risiconiveau

V1 bevat niet:

- publieke SaaS-distributie
- teamfunctionaliteit
- marketplace
- volledige mobiele app
- GPU-local-model productiegebruik tenzij hardware gevalideerd is
- UI die voelt als een normale chatbot of standaard dashboard

## 6. Kerngebruikersdoelen

De gebruiker wil:

- sneller relevante kennis vinden dan handmatig zoeken
- documenten, mail, calendar, web en projecten laten samenkomen in één knowledge graph
- ’s ochtends zien wat Leon heeft onderzocht, verbeterd, gevonden en voorgesteld
- Leon autonoom laten werken zonder secrets te lekken of rommel te maken
- controle houden via logs, rollback, policies en inspecteerbare details
- een interface ervaren die levend en intelligent voelt

## 7. Success Metric V1

Primaire succesmetric:

**Leon vindt relevante kennis sneller en bruikbaarder dan de gebruiker dit handmatig kan doen.**

Ondersteunende metrics:

- percentage correcte/relevante memory retrievals
- aantal nuttige morning brief-items per run
- aantal autonome acties zonder rollback nodig
- aantal acties met volledige diff/log/back-up
- tijd tot bruikbaar antwoord bij project- of documentvragen
- nul secrets/API keys zichtbaar in UI, logs of modelcontext

## 8. Non-Goals en Harde Grenzen

Harde non-goals:

- secrets, API keys, tokens of credentials zichtbaar tonen of lekken
- UI laten voelen als standaard chatbot, adminpanel of SaaS-dashboard

Extra productgrenzen:

- geen publieke exposure zonder expliciete policy
- geen permanente ontraceerbare wijzigingen
- geen autonome actie zonder audit trail
- geen memory-opslag zonder delete/scrub mogelijkheid
- geen verborgen modelkosten bij dure runs

## 9. Autonomiebeleid

Leon mag autonoom werken binnen ingestelde budgetten en risicoklassen.

Autonomie is niet “alles mag”. Autonomie betekent:

- Leon classificeert elke actie op risico
- Leon kiest model/tool/agent op basis van taakcomplexiteit
- Leon bewaart intent, input, output, diff, log en rollback-informatie
- Leon toont dure of risicovolle acties adaptief in de UI
- Leon stopt of vraagt confirmation wanneer policy dat vereist

## 10. Risico- en Rollback Ladder

### R0: Read-only

Voorbeelden:

- documenten lezen
- repo analyseren
- mail/calendar/browserhistorie indexeren
- web research
- memory retrieval

Toegestaan:

- autonoom uitvoeren
- logging verplicht
- bronverwijzing verplicht

Rollback:

- niet nodig, maar index-entry moet delete/scrub ondersteunen

### R1: Lokale tijdelijke verwerking

Voorbeelden:

- samenvattingen maken
- embeddings genereren
- graph edges voorstellen
- tijdelijke cache bouwen

Toegestaan:

- autonoom uitvoeren

Rollback:

- cache/delete support verplicht

### R2: Lokale persistente wijzigingen

Voorbeelden:

- memory opslaan
- graph-node toevoegen
- taak aanmaken
- lokale config aanpassen binnen veilige grenzen

Toegestaan:

- autonoom binnen policy

Rollback:

- before/after snapshot verplicht
- undo/delete/scrub verplicht

### R3: Lokale code- of systeemwijzigingen

Voorbeelden:

- scripts verbeteren
- tests toevoegen
- kleine refactors
- night-improvement patches

Toegestaan:

- autonoom als tests slagen en diff beperkt is

Rollback:

- git diff of patch snapshot verplicht
- testresultaten verplicht
- morning brief moet wijziging melden

### R4: Externe write-acties

Voorbeelden:

- mail sturen
- calendar event aanpassen
- browser automation met accountstatus
- externe tooldata wijzigen

Toegestaan:

- autonoom alleen als connector-policy dit expliciet toestaat

Rollback:

- waar mogelijk compensating action
- volledige audit trail
- preview in morning brief of live activity panel

### R5: Geld, accounts, public exposure, secrets, installs

Voorbeelden:

- betalingen
- cloudkosten
- public deploy
- API-key wijzigingen
- package installs
- model downloads
- account permissions

Toegestaan:

- standaard geblokkeerd of explicit approval
- kan later per policy worden versoepeld

Rollback:

- verplicht plan vooraf
- audit verplicht
- approval/event-log verplicht

## 11. Night Queue

De night queue is de eerste kernfeature.

Doel:

Leon werkt ’s nachts autonoom aan onderzoek, memory, verbeteringen en kansen binnen ingestelde risicoklassen.

Night queue taken:

- documenten en nieuwe bronnen indexeren
- knowledge graph verrijken
- projectcontext updaten
- ontbrekende componenten of tools detecteren
- kleine lokale verbeteringen uitvoeren als policy dit toestaat
- tests draaien na lokale wijzigingen
- kansen, bugs, risico’s en ideeën verzamelen
- dure of risicovolle acties voorbereiden als proposal

De night queue moet nooit stil of onzichtbaar “magisch” werken. Elke run heeft:

- run id
- start/eindtijd
- agent/model keuzes
- kostenindicatie
- acties per risicoklasse
- bronlijst
- wijzigingen
- failures
- rollback status
- morning brief output

## 12. Morning Brief

Morning brief is automatisch beschikbaar na een night run en handmatig opvraagbaar.

Inhoud:

- wat Leon heeft onderzocht
- wat Leon heeft geleerd
- welke memory/graph updates zijn gedaan
- welke kleine verbeteringen zijn uitgevoerd
- welke acties aandacht vragen
- welke kansen of ideeën zijn gevonden
- welke risico’s, fouten of blockers bestaan
- kostenwaarschuwingen indien relevant

De morning brief moet standaard rustig zijn, met openklapbare details.

Belangrijke UI-secties:

- “Belangrijk vandaag”
- “Nieuwe kennis”
- “Uitgevoerde verbeteringen”
- “Voorstellen”
- “Risico’s/aandacht”
- “Kosten en modellen”
- “Bronnen en logs”

## 13. Memory en Knowledge Graph

V1 vereist een brede persoonlijke kennislaag.

Databronnen:

- lokale documenten
- projectbestanden
- repo docs
- mail
- calendar
- browser/web research
- taken
- personen
- projecten
- tools
- eerdere Leon-runs

Graph entiteiten:

- document
- project
- task
- person
- organization
- decision
- memory
- source
- tool
- agent run
- workflow
- risk
- approval
- component

Graph relaties:

- belongs_to
- mentions
- depends_on
- derived_from
- conflicts_with
- supersedes
- requested_by
- generated_by
- approved_by
- blocked_by
- related_to

Memory requirements:

- elke memory heeft bron/provenance
- elke memory heeft confidence
- elke memory heeft created_at/updated_at
- elke memory is verwijderbaar
- credential-achtige content wordt geblokkeerd
- conflicting memories worden zichtbaar gemarkeerd
- Leon mag leren uit gebruik, maar moet correctie/undo ondersteunen

## 14. Integraties

V1 mag mail, calendar, browser en tools volledig gebruiken binnen risicoklassen.

Connector requirements:

- elke connector heeft permissions manifest
- read/write scopes zijn apart
- denied-write tests verplicht
- secrets nooit tonen
- externe writes krijgen risico-classificatie
- connectoracties worden gelogd
- connector failures verschijnen in morning brief

Prioriteit:

1. lokale documenten/projecten
2. browser/web research
3. mail read/write volgens policy
4. calendar read/write volgens policy
5. MCP/tool connectors
6. finance/shopper/ticket/voice later

## 15. Modelstrategie

Leon gebruikt OpenAI cloudmodellen als primaire route.

Later worden lokale GPU-modellen toegevoegd zodra hardware gevalideerd is.

Routingprincipes:

- goedkoop model voor simpele classificatie, extractie en housekeeping
- balanced model voor normale agenttaken
- premium model voor complexe planning, code review, architectuur en gevoelige beslissingen
- lokale GPU-modellen alleen na benchmark, driver/CUDA-check en kwaliteitsvalidatie

Kostenbeleid:

- geen harde limiet als default
- waarschuwingen bij dure acties
- kosten per run zichtbaar
- premium route moet verklaarbaar zijn

## 16. Agent Orchestration

Leon stuurt agents aan op basis van taakgrootte, risico en benodigde kwaliteit.

Agentrollen:

- Planner Agent
- Research Agent
- Memory Agent
- Code/Improvement Agent
- Review Agent
- Tool/Connector Agent
- UI Composition Agent
- Safety/Governance Agent

Elke agent-run bevat:

- taak
- modelroute
- inputbronnen
- output
- confidence
- kostenindicatie
- risico-inschatting
- reviewer/resultaat
- vervolgactie

Voor risicovolle acties moet een Review Agent of policy gate worden gebruikt.

## 17. UI Requirements

V1 bevat de eerste echte Leon UI.

Structuur:

- modulair canvas
- bottom floating dock
- levende Leon character/entity
- dynamic component composition
- adaptive transparency
- morning brief als centrale startinterface
- memory graph views
- project/context views

Geen permanente traditionele sidebar.

Primaire spaces:

- Home
- Chat
- Workflows
- Memory
- Skills
- Projects
- Settings

Deze voelen als verbonden ruimtes, niet als losse webpagina’s.

## 18. Leon Character

Leon heeft een klein herkenbaar digitaal personage.

Eigenschappen:

- minimalistisch
- vriendelijk
- zachte 2D/3D-combinatie
- niet realistisch menselijk
- subtiele glow
- functioneel gekoppeld aan systeemstatus

States:

- Idle: rustig zweven/ademen
- Thinking: focus-glow en subtiele particles
- Acting: beweegt naar actief component
- Interacting: activeert of verplaatst visueel componenten
- Sleeping: gedimd en bijna stil
- Attention: amber accent bij review of risico
- Error: rood alleen bij echte fout/gevaar

Het personage is geen decoratie. Het toont waar Leon mee bezig is.

## 19. UI Composition

Leon genereert niet willekeurig nieuwe UI. Leon stelt schermen samen uit vooraf ontworpen componenten.

Componenttypes:

- cards
- panels
- timelines
- workflow nodes
- graphs
- inspectors
- memory views
- action blocks
- lists
- media/tool blocks
- morning brief sections
- approval panels
- run logs
- source inspectors

Missing Component Protocol:

- als een component ontbreekt, gebruikt Leon tijdelijk beste alternatief
- ontbrekende component wordt als development task geregistreerd
- morning brief kan ontbrekende UI-capabilities tonen

## 20. Animatie en Interactie

Animaties moeten functioneel zijn.

Requirements:

- vloeiende transities
- spring/physics motion
- geen harde pagina-overgangen
- cards kunnen uitgroeien tot detailvensters
- panelen kunnen samenvoegen/splitsen
- elementen bewegen magnetisch naar logische posities
- visuele continuïteit blijft behouden
- geen drukke of irritante animaties

## 21. Transparantie

Leon is standaard rustig, maar details zijn openklapbaar.

Standaard zichtbaar:

- status
- voortgang
- eindresultaat
- risico/attention signalen

Openklapbaar:

- bronnen
- modelkeuze
- kosten
- prompts/samenvattingen
- logs
- diffs
- graph updates
- policy decisions
- rollback data

## 22. Acceptatiecriteria V1

V1 is acceptabel wanneer:

- night queue autonoom draait binnen risicoklassen
- morning brief automatisch na night run beschikbaar is
- memory graph meerdere databronnen kan indexeren
- relevante kennis sneller vindbaar is dan handmatig zoeken
- secrets niet zichtbaar worden in UI/logs/modelcontext
- UI niet voelt als chatbot/dashboard
- Leon character status correct representeert
- dure acties waarschuwingen geven
- lokale wijzigingen diff/log/rollback hebben
- externe acties via connector-policy lopen
- tests aantonen dat denied-write, secret scanning en audit logging werken

## 23. Technische Deliverables

V1 deliverables:

- `night_queue` scheduler/service
- `agent_run` execution model
- `risk_policy` engine
- `rollback_registry`
- `morning_brief` generator
- `memory_graph` expanded schema
- document/mail/calendar/browser ingestion pipelines
- connector permission manifests
- model routing implementation
- cost warning layer
- UI composition runtime
- Leon canvas shell
- bottom dock
- Leon character state renderer
- source/log/diff inspectors
- test suite for governance, memory, connectors and UI state

## 24. Belangrijkste Risico’s

Risico’s:

- te veel autonomie zonder duidelijke rollback
- memory graph wordt rommelig of onbetrouwbaar
- secrets komen per ongeluk in logs/modelcontext
- UI wordt alsnog een dashboard
- externe connector writes zijn moeilijk betrouwbaar terug te draaien
- kosten kunnen oplopen zonder harde limieten
- lokale GPU-route kan meer complexiteit geven dan waarde

Mitigaties:

- risk ladder verplicht
- provenance/confidence per memory
- secret scanner in ingestion en logging
- UI design constraints hard vastleggen
- connector write-tests
- cost warnings
- GPU pas na validatie

## 25. Fasering

### Phase 1: Night Queue + Morning Brief

- autonomous scheduler
- risk policies
- morning brief
- run logs
- cost warnings
- rollback registry

### Phase 2: Memory Graph Expansion

- brede ingestion
- graph schema uitbreiden
- retrieval UX
- confidence/provenance
- delete/scrub/correction

### Phase 3: Living Leon UI

- canvas shell
- dock
- character states
- component composition
- memory and brief visualizations

### Phase 4: Tool Integrations

- mail/calendar/browser
- MCP connectors
- write policies
- denied-write tests
- connector audit

### Phase 5: Advanced Autonomy

- self-improvement loops
- automated small fixes
- agent review chains
- richer workflow automation

### Phase 6: Local GPU Route

- hardware validation
- model benchmark
- routing integration
- quality/cost comparison

## 26. Final Product Principle

Leon mag technisch complex zijn, maar moet voor de gebruiker rustig voelen.

De gebruiker ziet geen losse verzameling scripts, agents en dashboards. De gebruiker ervaart één levende AI-omgeving die begrijpt wat belangrijk is, kennis terugvindt, werk voorbereidt, zichzelf verbetert en altijd traceerbaar blijft.