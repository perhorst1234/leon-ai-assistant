# OpenAI Agents SDK sandbox plan

Status: plan-only  
Datum: 2026-08-01  
Beslissing uit reuse review: `sandbox_before_decision`

Dit document beschrijft de eerste veilige sandbox voor OpenAI Agents SDK als Leon runtime-adapter kandidaat. Dit is geen installatie-opdracht, geen provider-enable, geen approval en geen runtime-promotie. Uitvoering van dit plan vereist later een expliciete approval voor install/API-gebruik.

## Doel

Bewijs leveren dat OpenAI Agents SDK achter Leon’s bestaande control-plane gates kan draaien zonder deze te omzeilen:

- `agent_assignment_proposals` blijven de startpoort;
- `local_mock` blijft fallback en default;
- alleen env-key presence wordt gecontroleerd;
- toolcalls blijven onder Leon permission preflight;
- agent-output blijft reviewbaar vóór acceptatie;
- audit events blijven append-only en redacted.

## Bronnen

- Lokale beslissing: `docs/agent-runtime-provider-decision.md`
- Lokale providerconfig: `config/agent-runtime-provider.json`
- Lokale kandidaat: `config/tool-catalog.candidates.json`
- OpenAI Agents SDK guide: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents SDK Python docs: https://openai.github.io/openai-agents-python/
- Guardrails docs: https://openai.github.io/openai-agents-python/guardrails/
- Tools docs: https://openai.github.io/openai-agents-python/tools/
- License: https://raw.githubusercontent.com/openai/openai-agents-python/main/LICENSE
- Security policy: https://raw.githubusercontent.com/openai/openai-agents-python/main/SECURITY.md

## Scope van de eerste sandbox

Toegestaan na expliciete sandbox-approval:

- disposable Python venv of container buiten runtime-critical pad;
- dependency pin in sandbox-only requirements/lock;
- één text-only agent run zonder tools;
- één lokale custom function-tool demo met Leon preflight vóór uitvoering;
- audit-only tracing test met redaction of tracing disabled;
- rollback-test naar `local_mock`.

Niet toegestaan in de eerste sandbox:

- ShellTool;
- ApplyPatchTool;
- ComputerTool;
- hosted MCP;
- web/file/code hosted tools;
- browser automation;
- filesystem writes buiten disposable sandbox;
- echte externe writes;
- accountconnecties;
- GPU-heavy work;
- automatische manifest-promotie.

Extra gate: handoffs, sessions en tracing mogen geen bypass vormen rond Leon audit, review, modelrouting of permission preflight. Als de SDK intern state of traces bijhoudt, blijft Leon’s control plane leidend voor taakstatus, evidence, reviewerbesluit en rollback.

## Secret handling

Required env-key naam:

- `OPENAI_API_KEY`

Regels:

- Leon mag alleen presence/status tonen.
- De sandboxadapter krijgt een scoped client of runtime capability, niet raw `.env.local`.
- Geen keywaarde in prompt, task packet, audit payload, trace, logs, dashboard API of agent context.
- Bij ontbrekende key: taakstatus wordt `waiting_for_secret`; geen poging tot provider-call.

## Adapter lifecycle

1. Reviewer maakt een sandbox approval-card voor install/API-gebruik.
2. Na approval wordt een disposable sandboxomgeving voorbereid.
3. Providerconfig blijft `local_mock` default; nieuwe adapter staat `disabled`.
4. Sandbox voert eerst alleen een dry-run adapterplan uit.
5. Daarna volgt één text-only provider call met laag-risico prompt.
6. Daarna volgt één custom function-tool demo waarbij Leon permission preflight eerst beslist.
7. Resultaat gaat naar `waiting_for_review`; geen automatische acceptatie.
8. Rollback wordt uitgevoerd en bewezen.

## Required audit events

Bij latere uitvoering moet de adapter minimaal vastleggen:

- `provider_sandbox_requested`
- `provider_sandbox_approved`
- `provider_adapter_dry_run_created`
- `provider_call_started`
- `provider_call_completed_or_failed`
- `provider_tool_preflight_checked`
- `provider_sandbox_rolled_back`

Payloadregels:

- redacted input;
- model/provider route en reden;
- env-key namen, geen waarden;
- approval id waar van toepassing;
- no raw tool arguments als die secrets of persoonlijke data bevatten.

## Acceptance tests voor latere uitvoering

De sandbox slaagt alleen als al deze punten bewezen zijn:

- `local_mock` blijft default vóór, tijdens en na sandbox.
- Ontbrekende `OPENAI_API_KEY` geeft `waiting_for_secret`, geen provider-call.
- Text-only run schrijft audit events en eindigt `waiting_for_review`.
- Custom function-tool call wordt vooraf door Leon permission policy beoordeeld.
- Een verboden tool/scope faalt vóór SDK-tooluitvoering.
- Prompt met fake secret wordt geredact in state/API/audit/trace.
- Geen ShellTool/ApplyPatchTool/ComputerTool/hosted tools/MCP beschikbaar.
- Audit hash-chain blijft valide.
- Rollback zet providerconfig terug naar alleen `local_mock` en verwijdert sandboxomgeving.

## Approval die later nodig is

Een latere sandbox-uitvoering vereist een approval-card met:

- actie: sandbox dependency install + één OpenAI API testcall;
- scope: alleen disposable sandbox, geen Leon repo runtime-mutatie;
- kosten: maximaal één laag-risico testcall binnen vooraf gekozen limiet;
- data: alleen testprompt, geen persoonlijke data;
- rollback: sandbox verwijderen en providerconfig op `local_mock`;
- expiry: korte geldigheid, éénmalig.

## Dashboard taak-uitkomst

De taak `Maak sandboxplan voor OpenAI Agents SDK adapter` mag op `done` wanneer dit document is vastgelegd en geverifieerd. Het plan zelf voert niets uit.
