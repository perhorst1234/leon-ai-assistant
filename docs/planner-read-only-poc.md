# Planner read-only proof of concept

Status: implemented  
Datum: 2026-08-01  
Scope: lokale sample-data, preview-only planning, geen externe acties.

## Doel

Deze PoC bewijst de eerste Planner Agent-laag zonder Gmail, Google Calendar, IMAP/SMTP, OAuth, MCP-install of echte accountdata te gebruiken.

De planner mag nu:

- sample calendar events lezen;
- sample mailmetadata/snippets lezen;
- conflicten detecteren;
- vrije slots vinden;
- conceptplanning voorstellen als preview.

De planner mag nu niet:

- MCP servers installeren of uitvoeren;
- Gmail/Calendar/IMAP/OAuth accounts koppelen;
- e-mail sturen, replyen, forwarden of draften in een extern account;
- agenda-events aanmaken, wijzigen, verwijderen of RSVP’en;
- mailbox-state wijzigen;
- secretwaarden lezen, loggen of tonen.

## Implementatie

- Engine: `src/leon_control_plane/planner_preview.py`
- API: `POST /api/planner/preview`
- Dashboard: kaart “Planner read-only PoC”
- Store/audit: `planner_previews` tabel en `planner_preview_created` audit-event

De sample fixture zit bewust embedded in de engine zodat deze PoC dependency-free blijft. De fixture bevat:

- meerdere calendar events;
- één bewust conflict;
- busy blocks;
- vrije slots;
- sample mailmetadata/snippets met meeting/deadline signalen.

## Contract

Elke preview bevat:

- `execution_allowed=false`
- `external_calls_made=false`
- `mcp_servers_installed=false`
- `accounts_connected=false`
- `secret_values_read=false`
- `write_allowed_now=false`
- `policy=read_only_sample_data_preview_only`
- conflicten;
- vrije slots;
- mail-signalen;
- preview proposals met source event/mail IDs;
- denied actions;
- approval gates voor latere echte writes.

Wanneer een request lijkt op schrijven, verzenden, connecten of installeren, blijft de output een preview maar krijgt het:

- `decision=write_or_connect_denied_preview_only`
- `approval_required=true`
- `required_gate=approval_card_required_before_external_write_or_connect`

## Tests

Gedekt in `tests/test_control_plane.py`:

- sample fixture parsing;
- conflictdetectie;
- free-slot detectie;
- preview proposal generation;
- denied send/connect/install/calendar-write path;
- denied raw-secret path;
- prompt-injection in sample mail kan scope niet uitbreiden;
- persistent store/audit blijft inert;
- HTTP API lekt geen secrets en maakt geen agent run/approval.

## Vervolg

Volgende veilige stap is een sandboxplan of mock-MCP adapter rond deze planner-output. Echte accountkoppeling mag pas na:

1. individueel MCP-server reviewtemplate;
2. manifestpromotie naar `approved_readonly`;
3. expliciete approval voor accountconnect;
4. denied-write tests met auditbewijs.
