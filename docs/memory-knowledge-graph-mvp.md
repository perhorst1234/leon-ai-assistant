# Memory en knowledge graph MVP

Datum: 2026-08-01  
Taak: `task-memory-en-knowledge-graph-mvp`  
Status: lokale MVP gebouwd; geen Mem0/Graphiti/Cognee/OpenViking install, geen vector database, geen embeddings, geen externe API.

## Productbesluit

De eerste memory-laag is bewust saai:

- SQLite in de bestaande control-plane store;
- review-first;
- zichtbaar in het dashboard;
- user-correctable;
- auditbaar;
- zonder externe services of verborgen profiling.

Dit is efficiënter en veiliger dan direct Mem0, Graphiti, Cognee of OpenViking installeren. Die projecten zijn waardevol, maar memory is een privacygevoelige kernlaag. Eerst moet Leon zelf delete/edit/review/confidence/source/expiry goed afdwingen.

## Wat is gebouwd

### Tabellen

- `memory_items`
- `memory_graph_edges`

### Memory item velden

Elk item bevat:

- `id`
- `status`: `candidate`, `active`, `rejected`, `deleted`
- `memory_type`: `session`, `working`, `long_term`, `episodic`, `negative`, `preference`, `project_fact`
- `content`
- `source`
- `source_task_id`
- `confidence`
- `sensitivity`: `low`, `medium`, `high`
- `privacy_level`: `normal`, `private`, `sensitive`
- `expires_at`
- `review_note`
- `correction_of`
- `graph_entities`
- audit/timestamps

### Graph edge velden

Elke relatie bevat:

- `source_memory_id`
- `subject`
- `predicate`
- `object`
- `confidence`
- `source`
- `status`
- audit/timestamps

## API

Nieuwe endpoints:

- `POST /api/memory`
- `POST /api/memory/update`
- `POST /api/memory/delete`
- `POST /api/memory/graph-edge`

`GET /api/state` toont:

- `memory_items`
- `memory_graph_edges`

Hierdoor is memory niet opaque: de gebruiker kan zien wat Leon onthoudt.

## Dashboard

Toegevoegd:

- Memory create form.
- Memory item lijst.
- Statusacties: activeer, reject, confidence omlaag, vergeet.
- Graph edge lijst.

Delete scrubt de inhoud:

- memory `content` wordt `[deleted]`;
- graph labels worden `[deleted]`;
- audit bewaart alleen redacted metadata.

## Veiligheidsbeleid

Nieuwe memory start standaard als `candidate`.

Active long-term/sensitive memory vereist een `review_note` wanneer:

- `memory_type=long_term`, of
- `sensitivity=high`, of
- `privacy_level=sensitive`.

Deze waarden worden geweigerd vóór opslag:

- OpenAI-achtige `sk-*` keys;
- Google-achtige `AIza...` keys;
- `api_key=...`;
- `token=...`;
- `password=...`;
- `secret=...`.

Audit events slaan geen memory content op, alleen metadata/counts.

## Buiten scope gehouden

Bewust niet gedaan:

- geen Mem0/Graphiti/Cognee/OpenViking install;
- geen Neo4j/vector DB;
- geen embeddings;
- geen document-ingestie;
- geen automatische long-term memory;
- geen externe API calls;
- geen accountkoppeling;
- geen hidden profiling;
- geen night-cycle memory writes.

## Externe kandidaten voor later

Als volgende stap kunnen deze kandidaten met dezelfde veilige dataset worden gesandboxed:

| Candidate | Repo | Score | Status |
| --- | --- | ---: | --- |
| Mem0 | `mem0ai/mem0` | 77 | `candidate` |
| Graphiti | `getzep/graphiti` | 76 | `candidate` |
| Cognee | `topoteretes/cognee` | 72 | `candidate` |
| OpenViking | `volcengine/OpenViking` | 65 | `candidate` |

Alle vier blijven install/connect/write/resource/spend gated.

## Verificatie

Toegevoegde tests bewijzen:

- schema/migration werkt;
- memory create/list/update/delete werkt;
- graph edges werken;
- sensitive long-term activation zonder review note faalt;
- credential-like memory wordt geweigerd;
- delete scrubt content en graph labels;
- HTTP API toont memory zichtbaar in state;
- audit hash-chain blijft geldig.
