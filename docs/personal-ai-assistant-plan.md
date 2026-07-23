# Personal AI Assistant — uitgewerkt conceptplan
# Gaia / Personal AI Assistant — uitgewerkt conceptplan

## 1. Productvisie

Het doel is een persoonlijke AI-assistent die niet alleen reageert op vragen, maar zichzelf structureel verbetert. Het systeem bestaat uit een snelle dagelijkse assistent, een zware researchlaag voor complexe taken en een nachtelijke verbetercyclus die leert van gesprekken, tools, fouten, kansen en terugkerende patronen.
Gaia is de werknaam voor een persoonlijke AI-assistent die niet alleen reageert op vragen, maar zichzelf structureel verbetert. Het systeem bestaat uit een snelle dagelijkse assistent, een zware researchlaag voor complexe taken, een contextuele UI/UX-laag en een nachtelijke verbetercyclus die leert van gesprekken, tools, fouten, kansen en terugkerende patronen.

De assistent moet drie dingen tegelijk kunnen:
De assistent moet vier dingen tegelijk kunnen:

1. **Direct helpen** bij eenvoudige vragen en kleine taken.
2. **Diep werken** aan grote opdrachten via gespecialiseerde agents en tools.
3. **Zichzelf verbeteren** door kansen in de buitenwereld en patronen in het eigen gedrag te analyseren.
4. **De juiste interface tonen** voor de taak, samengesteld uit vaste, betrouwbare componenten.

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
