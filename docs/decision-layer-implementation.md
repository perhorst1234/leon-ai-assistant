# Leon AI Assistant — Decision Layer + routing evals

Status: implemented MVP  
Scope: local deterministic router; no external calls, no OpenAI calls, no Codex execution.

## What this slice adds

- `src/leon_control_plane/decision_layer.py`
  - Classifies user prompts into exactly one route:
    - `direct_answer`
    - `clarification_required`
    - `quick_tool_use`
    - `memory_retrieval`
    - `shell_agent_flow`
    - `research_agent`
    - `task_queue`
    - `approval_required`
    - `refuse_redirect`
  - Estimates intent, complexity, risk, urgency, explainable value score, value band handling, execution path, required tools, expected output, source/tool need and confidence.
  - Uses the existing `choose_route()` model policy for Luna/Terra/Sol/local route metadata.
  - Redacts common secret patterns before API response, SQLite persistence or audit payload.

- `config/routing-evals.json`
  - 34 regression cases covering direct answer, clarification, read-only tool, memory retrieval, shell/agent flow, research, queue, approval and refusal routes.
  - Misroute regressions are kept in the same eval file with `source: "misroute_regression"` so future routing changes must preserve the corrected path.
  - Covers finance, mail, calendar, server, destructive filesystem, secret exfiltration, GPU/modeldownload and captcha/anti-bot cases.

- `scripts/leon-routing-eval`
  - Runs the routing evalset plus active feedback-promoted regression cases and exits non-zero on route mismatch.
  - Records release-labeled eval runs in SQLite by default; use `--no-record` for a pure local check.

- SQLite/API/dashboard
  - Adds `routing_decisions` table.
  - Adds `routing_eval_cases` for feedback-promoted routing failures.
  - Adds `routing_eval_runs` for release-scoped eval history, accuracy, safety failures and impact deltas.
  - Adds audit event `routing_decided`.
  - Persists `value_score_inputs` and `value_band` in `decision_json`, and copies score/band details into routing audit payloads for inspection.
  - Adds `POST /api/routing/decide`.
  - Adds `POST /api/routing/eval`.
  - Adds `POST /api/routing/eval-case`.
  - Dashboard shows recent route decisions, feedback counts, eval-case promotion, release eval history, score bands, score components, execution path details and explicitly says no action was executed.

## Safety boundaries

The Decision Layer only decides what should happen next. It does not:

- install dependencies;
- run external repositories;
- start GPU/model downloads;
- call OpenAI/Codex;
- connect accounts;
- send mail/calendar/payment/server writes;
- create executable tasks for refused requests.

Ambiguous prompts return `clarification_required` with questions and no executable work. Memory-context prompts return `memory_retrieval` with provenance expectations. Local code/repo work returns `shell_agent_flow` so it becomes a bounded agent task instead of a direct chat answer. High-impact prompts return `approval_required` with an approval payload. Unsafe prompts return `refuse_redirect`.

## Feedback-to-eval loop

Routing feedback remains append-only in `decision_feedback`. When a decision is marked wrong or risky, the reviewed failure can be promoted into `routing_eval_cases` with the expected route, actual recorded route, source feedback id, failure type and reason. Active promoted cases are merged with `config/routing-evals.json` for future eval runs.

Eval summaries now report route accuracy, failed case ids, safety false negatives for `approval_required` and `refuse_redirect` cases, a routing logic fingerprint, and release impact versus the previous recorded eval run. `routing_eval_runs` persists these summaries by release label so decision logic changes can show whether routing quality improved or regressed and whether safety failures were introduced.

## Execution paths

`execution_path` is stored in `decision_json` and copied into routing audit details. It records the path type, next step, selected agent role when relevant, required tools, selected model route, and whether execution is allowed now.

Path types:

| Route | Path |
|---|---|
| `direct_answer` | `local_handling` |
| `quick_tool_use` | `local_tool` |
| `memory_retrieval` | `memory_retrieval` |
| `shell_agent_flow` | `shell_agent_flow` |
| `research_agent` | `agent_flow` |
| `task_queue` | `queue` |
| `approval_required` | `approval` |
| `clarification_required` | `clarification` |
| `refuse_redirect` | `safe_refusal` |

## Value score bands

Each decision includes `value_score_inputs` with additive components and `value_band` with the resulting handling:

| Score | Default handling |
|---:|---|
| 0-24 | `ignored` |
| 25-49 | `queued` |
| 50-69 | `proposed` |
| 70-89 | `executed` when the route is immediate and safe |
| 90-100 | `held_for_approval` |

Risk policy can override the default band handling. Unsafe requests are ignored/refused, high-risk or review-required requests are held for approval, and deferred work remains queued.

## Risk classes

Every action is assigned one risk class from R1-R5 before execution. Each class carries concrete examples in `RISK_CLASSES`, and policy results include `risk_rationale`, `approval_state`, `approval_first_required`, rollback requirements and audit-required status.

| Class | Meaning | Examples |
|---|---|---|
| `R1` | Read-only or local temporary processing | direct answer, local status read, delete-capable cache |
| `R2` | Local persistent change | local task, reviewed memory/source metadata, local non-secret config |
| `R3` | Local code or system change | project file patch, bounded workspace-changing shell command, code change with tests |
| `R4` | External write action | send mail, calendar mutation, GitHub issue write, public post |
| `R5` | Money, accounts, public exposure, secrets, installs | purchase/trade, account connection, permission change, install/model download, raw-secret action |

`R4` and `R5` are approval-first. Without a consumed approval they return `approval_state: "required_before_action"` and cannot execute; hard-blocked unsafe secret/abuse actions return `approval_state: "not_approvable"`. Approval requests persist the expected change, risk class, rollback plan, failure mode and a plan fingerprint. Rejected fingerprints cannot be applied again without changing the proposed plan.

## Acceptance checks

Required checks:

```bash
PYTHONPATH=/home/per/leon-ai-assistant/src python3 -m py_compile \
  src/leon_control_plane/server.py \
  src/leon_control_plane/store.py \
  src/leon_control_plane/model_policy.py \
  src/leon_control_plane/decision_layer.py \
  src/leon_control_plane/agent_runtime.py \
  tests/test_control_plane.py

PYTHONPATH=/home/per/leon-ai-assistant/src python3 tests/test_control_plane.py
./scripts/leon-routing-eval --no-record
```

Manual API checks:

```bash
curl -fsS -X POST http://127.0.0.1:8765/api/routing/decide \
  -H 'content-type: application/json' \
  -d '{"text":"Installeer n8n."}'

curl -fsS -X POST http://127.0.0.1:8765/api/audit/validate \
  -H 'content-type: application/json' \
  -d '{}'
```
