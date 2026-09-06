# UI Composition en assistant character foundation

Datum: 2026-08-01  
Taak: `task-ui-composition-en-assistant-character-foundation`  
Status: foundation gebouwd; geen definitieve chat UI, geen nieuwe frontend stack, geen complexe avatar/motion.

## Productbesluit

Deze slice legt de UI-grammatica vast, niet de uiteindelijke Leon Assistant interface.

De gebruiker gaf eerder expliciet aan dat het geen simpele AI assistant UI wordt en dat de echte UI later gespecificeerd wordt. Daarom is hier gebouwd:

- declaratieve spaces;
- Component DNA registry;
- route/status → compositieregels;
- assistant character als statuslaag;
- frictie- en safetyregels;
- read-only preview in dashboard/API.

Niet gebouwd:

- definitieve chatervaring;
- message persistence;
- realtime canvas;
- humanoid/avatar;
- motion system;
- React/Tauri/andere frontend stack.

## Implementatie

### Config

`config/ui-composition.json`

Bevat:

- `spaces`
- `component_registry`
- `assistant_states`
- `composition_rules`
- `task_status_rules`
- `friction_metrics`
- `safety_invariants`

### Composer

`src/leon_control_plane/ui_composition.py`

Functie:

- `compose_ui(...)`

Eigenschappen:

- preview-only;
- `execution_allowed=false`;
- onbekende routes/components activeren Missing Component Protocol;
- high-risk/approval routes krijgen altijd frictie;
- secrets/missing env routes tonen `SecretIntakeCard`;
- motion is tekstueel en subtiel/none.

### API

`POST /api/ui/compose`

Maakt een compositie-preview. Dit muteert geen projectstate en voert niets uit.

### Dashboard

Toegevoegd:

- “UI Composition foundation” kaart;
- live composition preview;
- spaces-overzicht;
- component-DNA registry count;
- assistant statuslabel/motion/frictie/safety-notes.

`GET /api/state` bevat:

- `ui_composition_policy`
- `ui_composition_preview`

## Spaces

Eerste set:

- `home`
- `chat`
- `research`
- `workflow`
- `memory`
- `tools`
- `settings`

Deze zijn ruimtes, geen definitieve pagina’s. De uiteindelijke interface mag later anders visualiseren, zolang de safety states behouden blijven.

## Assistant character

De assistant character is nu alleen statuslaag:

- `idle`
- `thinking`
- `researching`
- `waiting_for_approval`
- `waiting_for_secret`
- `blocked`
- `reviewing`
- `done`

Regels:

- status heeft altijd tekstlabel;
- motion is `none` of `subtle`;
- motion draagt geen essentiële informatie;
- approval/waiting/risk mag nooit visueel voelen als executed/done;
- character mag de primaire taak niet verstoren.

## Component DNA

Elk component declareert:

- doel;
- allowed spaces;
- required state;
- safety role.

Voorbeelden:

- `ApprovalSheet`: approval gate;
- `SecretIntakeCard`: secret safety;
- `MemoryCard`: user control;
- `PermissionCheckCard`: tool safety;
- `AuditRow`: evidence;
- `ResearchBoard`: method/status;
- `SourceStack`: provenance;
- `AssistantStatusPill`: status.

## Missing Component Protocol

Als Leon een UI nodig heeft die niet geregistreerd is:

1. geen ad-hoc component renderen;
2. dichtstbijzijnde veilige componenten gebruiken;
3. `missing_component_protocol=true`;
4. `UncertaintyCard`/`ContextCard` tonen;
5. later een component-task maken als het echt nodig is.

High-risk flows mogen nooit met onbekende custom UI doorlopen.

## Frictiemetrics

Eerste signalen:

- `approval_required`;
- `missing_secret`;
- `blocked_task`;
- `review_needed`;
- `high_risk_route`;
- `hidden_component_needed`;
- `too_many_primary_components`.

Doel:

- simpele taken compact houden;
- complexe taken plan/status/bron/onzekerheid tonen;
- approval clarity verhogen;
- follow-up burden verlagen;
- component overload voorkomen.

## Safety invariants

Uit `config/ui-composition.json`:

- approval actions must be explicit and accessible;
- secret values must never render;
- high-risk flows must include an approval or policy component;
- memory must remain inspectable and editable;
- tool execution state must never be implied when `execution_allowed=false`;
- motion must be subtle or disabled and never carry essential information.

## Verificatie

Tests bewijzen:

- approval routes tonen `waiting_for_approval` en `ApprovalSheet`;
- unknown components activeren Missing Component Protocol;
- missing secret route toont settings/`SecretIntakeCard`;
- `/api/ui/compose` is inert en `execution_allowed=false`;
- `/api/state` bevat UI policy/preview zonder secretwaarden;
- bestaande auth/secret/task/audit/routing tests blijven groen.
