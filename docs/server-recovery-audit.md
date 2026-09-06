# Servercode-inventaris — 6 september 2026

## Uitkomst

De gebruiker heeft twee leesbare Windows-mappen aangeleverd: `Documents/leon-ai-assistant` en `Documents/leon-workspace`. De eerste bevat echte Python-backendcode en een lokale Git-geschiedenis. De tweede bevat ondersteunende agent-/researchwerkruimtes en voorbeelden, geen tweede applicatierepository.

**De export is onvolledig.** Dit is een code-inventaris en gedeeltelijke back-up, geen bevestiging dat de server kan starten of dat alle laatste wijzigingen zijn veiliggesteld. De oorspronkelijke aangeleverde mappen worden als bron behouden.

De gecontroleerde bronkopie wordt bewaard op [de herstelbranch](https://github.com/perhorst1234/leon-ai-assistant/tree/codex/ssd-recovery-2026-09-06). `main` bevat de frontend en actuele overdrachtsdocumentatie; de onvolledige backend wordt nog niet als geïntegreerde release samengevoegd.

## Git en ontbrekende bestanden

- Server-HEAD: `6b1863b6e1fdc612672c816ac048313c677115ca`, commitdatum 9 augustus 2026.
- Gemeenschappelijke basis met GitHub: `d0f7ba0a99227c37fef6c67cc1948d270217ac8a`.
- **16 lokale commits** na die basis stonden nog niet op GitHub. Daarnaast zijn er inhoudelijke ongecommitte wijzigingen, onder meer circa 587 toegevoegde regels in `decision_layer.py` en 251 in `model_policy.py`.
- De scripts verloren bij de Windows-export hun executable-bit; zes van de zeven scriptwijzigingen zijn alleen dat modeverschil. `leon-routing-eval` heeft ook gewijzigde inhoud. De herstelbranch behoudt de oorspronkelijke `100755`-modus.
- `git fsck --full --no-reflogs --no-dangling` meldt exact één ontbrekend Git-object: blob `c23bfd252bc957407403c5abda3fc2d654df7aa7`, de `store.py`-versie van HEAD. Een volledige Git-clone/push van deze lokale geschiedenis is daardoor niet betrouwbaar mogelijk.

| Ontbreekt in werkmap | Aanwezige historie | Nodig voor volledig herstel |
|---|---|---|
| `src/leon_control_plane/server.py` | HEAD-blob bestaat, 186.101 bytes | Actuele werkmapversie van SSD, inclusief ongecommitte werk |
| `src/leon_control_plane/store.py` | HEAD-blob ontbreekt; oudere versies bestaan | Actuele SSD-versie én ontbrekend Git-object om de oorspronkelijke geschiedenis volledig te maken |
| `tests/test_control_plane.py` | HEAD-blob bestaat, 189.848 bytes | Actuele testversie van SSD |
| `docs/personal-ai-assistant-plan.md` | HEAD-blob bestaat, 84.555 bytes | Actuele SSD-versie vergelijken; GitHub-plan is afzonderlijk behouden |

Ook enkele tijdelijke Ralph-bestanden ontbreken; die zijn geen broncode en worden niet opnieuw aangemaakt. Het ontbreken van grote bronbestanden kan door de export komen, maar de precieze oorzaak is nog niet bevestigd. Oudere Git-versies zijn niet stilzwijgend als actuele bestanden teruggezet.

## Wat aantoonbaar bestaat

| Onderdeel | Bewijs in de aangeleverde bron | Wat dit nog niet bewijst |
|---|---|---|
| Python control plane | `pyproject.toml`, 22 aanwezige Python-modules, dashboardscripts en implementatiedocumenten | Een startende HTTP-server; server/store ontbreken in de werkmap |
| Decision Layer / Value Engine | Classificatie, signalen, waardeweging, verduidelijking, uitvoeringsroute en evaluatiefuncties in `decision_layer.py` | Algemene modelintelligentie of foutloze classificatie buiten de testset |
| Modelrouter | Kosten/privacy/budget, lokale validatie en fout-/latencyfallback in `model_policy.py` | Werkelijke providercalls, kostenmeting of draaiend GPU-model |
| Agentmodel en orchestration | Taakpakketten, roltoewijzing, reviewcontract, voorstellen, `MockAgentRunner` | Echte urenlange agentuitvoering; de runner is expliciet deterministisch/mock |
| OpenAI-adapter | `build_openai_agents_sdk_dry_run_plan`, gekozen Python-SDK als eerste doel | SDK-installatie of echte calls; `execution_allowed` en `provider_calls_made` zijn false |
| Taken, approvals, audit, rollback | Implementatiedocumenten, imports en store-call-sites; SQLite staat beschreven | Actuele opslagimplementatie en crash-/herstartgedrag; centrale store ontbreekt |
| Memory/graph/retrieval | Gedocumenteerde SQLite-MVP, contextverwerking en code die memories gebruikt | Een nu geteste duurzame database, embeddings of externe memorydienst |
| Night Queue / Morning Brief | `NightQueueScheduler.run_once`, lokale acties, voorstellen, rapportgeneratie | Een geïnstalleerde timer, echte self-learning, autonome codewijzigingen of duurzame hervatting |
| Tool/MCP/connectorbeheer | Manifesten, scope-/risicoclassificatie, hergebruikscore, kandidaatcatalogus en GitHub-metadatafunctie | Geïnstalleerde MCP-servers of echte bank/mail/shop-integraties |
| Planner | `planner_preview.py` verwerkt sample-agenda en sample-mail | Een echte agenda-/mailkoppeling |
| UI-compositie / transparantie | Canvas-/componentcontracten, statusafleiding en inspectorpayloads | Integratie met de afzonderlijk gemaakte Gaia-frontend |
| GPU | M40-readinessplan en validatiebeleid | Lokale inference: de configuratie bevat nog `not_run`-checks |

## Bevindingen die eerst aandacht vragen

### P0 — Volledigheid van de serverkopie

Herstel de drie essentiële bron/testbestanden en het ontbrekende Git-object vóór startup, grote refactors of uitspraken over volledige testdekking. Het aangeleverde `state` bevat een seed en een oud JSON-bestand, maar geen `control-plane.sqlite`. Bestaande taken, memories en auditgeschiedenis zijn dus evenmin als runtimeback-up aangetoond.

### P1 — Nachtwerk registreert testbewijs dat niet uitgevoerd wordt

`night_queue.py` zet in `build_night_queue_actions` voor `apply_controlled_self_improvement` vooraf `tests_passed=True`. De uitvoeringsbranch bouwt vervolgens een vaste patchtekst en `test_results` met `status="passed"` en `exit_code=0`, waarna die naar de store gaan. In die branch wordt geen testproces gestart. Dit is geen bewijs van een toegepast en getest codevoorstel. De code is bij deze audit behouden; de correctie en regressietest zijn als open werk geregistreerd.

### P1 — Configuratiekeuze is nog geen werkende provider

De huidige runner is `MockAgentRunner`; de OpenAI-SDK-adapter is een inert dry-runplan. Een modelnaam, gekozen route of geschat bedrag in het dashboard mag niet als echte modeluitvoering of gemeten kosten worden getoond.

### P1 — Volledige approvalketen opnieuw verifiëren

Het risicobeleid accepteert caller-input zoals `risk_class`, `explicit_approval`, `approval_status` en `tests_passed`. Dat hoeft intern niet verkeerd te zijn, maar echte veiligheid hangt af van wie deze velden mag invullen en of de store het approvalrecord aan de concrete actie bindt. Die HTTP/store-keten kan door de ontbrekende bestanden nog niet worden gecontroleerd. De seed bevat historische approvalstatus; dit is geen nieuwe toestemming voor een andere computer of actie.

## Actuele planning versus oude statusclaims

`tasks/prd.json` wijst naar **Phase 4 — Volledig Bruikbare Personal AI Environment** en bevat tien stories, allemaal `passes=false`. Een lokale samenvatting van 17 augustus vermeldt `INTERRUPTED`, nul iteraties en 0/10 afgerond. De eerdere samenvatting van 8 augustus noemt een afgeronde run, maar de teller `24/0` is inconsistent. Deze historische logs zijn geen acceptatiebewijs en worden niet openbaar gekopieerd.

Phase 4 voegt ook **GPU-temperatuurgestuurde chassisventilatorregeling** toe. Daarvoor is nog geen script/service in de aangeleverde bron gevonden. Het Phase-4-document noemt een **M40 24GB**; dit is documentatiebewijs, geen huidige hardwaremeting.

## Nieuwe controles in deze sessie

- Python 3.14: AST/syntaxcontrole van alle 22 aanwezige modules geslaagd, zonder de server te starten.
- De bestaande `evaluate_cases(load_eval_cases())`-set rechtstreeks uitgevoerd: **34/34 geslaagd**, inclusief 15 gate-gerelateerde gevallen en nul door de evaluator gerapporteerde safety failures. Geen API-calls of databasewrites.
- Volledige HTTP/store-tests: niet uitgevoerd; actuele testfile en store ontbreken. Afwezigheid van tests telt niet als slagen.
- De geselecteerde bronkopie is per bestand met SHA-256 vergeleken. Alleen twee documentatiebestanden zijn voor publicatie aangepast om een privétailnethostnaam te vervangen; de manifestdata legt dit onderscheid vast.
- Gerichte controle op veelvoorkomende credentialpatronen in geselecteerde bron en docs: geen matches. Geen volledige security-audit.
- `.env.local`, databases, runtime-JSON, agentlogs, private onderzoeks-/agenda-output, caches en lokale agentconfiguratie zijn uitgesloten van de openbare snapshot. Credentials zijn niet uitgelezen.
- `leon-workspace` bevat ondersteunende agentinstructies, een researchindex en test-/runmateriaal. Geen zelfstandige backend of alternatief `store.py` gevonden; deze werkruimte blijft lokaal.

## Hervatten

1. Maak de SSD-export compleet, bewaar de originele mappen en controleer Git-objectintegriteit opnieuw.
2. Vergelijk de nieuwe werkmapbestanden met de herstelbranch en behoud ongecommitte verschillen.
3. Herstel de oorspronkelijke Python/SQLite-stack in een aparte werkkopie en voer de volledige bestaande tests uit met tijdelijke state en synthetische credentials.
4. Corrigeer de nachtelijke schijntestresultaten voordat echte self-improvement wordt aangezet.
5. Koppel daarna de bestaande Gaia-Werk-UI aan echte backend-events en duurzame checkpoints. Kies geen nieuwe backendstack zonder concrete noodzaak.

Voor de originele commitnamen, bestandschecksums en publicatieafwijkingen: zie `docs/server-recovery-manifest.json` op de herstelbranch. De oorspronkelijke 16 commits blijven in de aangeleverde lokale `.git`; GitHub krijgt een gecontroleerde bron-snapshot, geen kopie van alle private ontwikkellogs uit die geschiedenis.
