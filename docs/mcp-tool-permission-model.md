# MCP / tool permission model

Status: v1 local control-plane gate.

Doel: Leon mag GitHub-repo’s, MCP-servers en lokale tools efficiënt hergebruiken, maar nooit als losse ongecontroleerde executiepad. Elke kandidaat begint als manifest. Elke toolactie krijgt eerst een permission check. De check voert niets uit.

## Bronnen

- MCP specification 2025-06-18: https://modelcontextprotocol.io/specification/2025-06-18
- MCP security best practices: https://modelcontextprotocol.io/specification/draft/basic/security_best_practices
- MCP announcement/context: https://www.anthropic.com/news/model-context-protocol

## Manifestvelden

Een tool/MCP-server wordt lokaal geregistreerd met:

- `tool_id`, `name`, `source_type`, `source_url`
- `purpose`, `owner`, `maintenance_status`
- `status`: `candidate`, `reviewed`, `approved_readonly`, `approved_write_gated`, `rejected`
- `risk_level`: `low`, `medium`, `high`, `critical`
- `read_scopes`, `write_scopes`
- `required_env_keys`
- `cost_profile`, `resource_profile`, `external_effects`
- `approval_required_for`
- `allowed_without_approval`
- `forbidden_actions`
- `rollback_notes`, `sandbox_required`, `notes`

Repo’s uit het productplan worden dus niet automatisch geïnstalleerd. Ze worden candidate manifests met bronlink, use-case, scope en risico. Installeren, verbinden, schrijven, geld uitgeven of zware GPU/downloadtaken blijven approval-gated.

De eerste compacte catalogus staat in `config/tool-catalog.candidates.json`. Die bevat alleen kernkandidaten uit het plan; de rest wordt later gescoord en toegevoegd als dat praktisch nodig is.

## Permission checks

Endpoint:

- `POST /api/tool-permissions/check`

Input:

```json
{
  "tool_id": "github-mcp-candidate",
  "action_type": "read",
  "requested_scope": "repo:metadata",
  "approval_id": null
}
```

Output bevat `decision`, `allowed`, `approval_required`, `required_gate`, `reason` en audit metadata.

Beslissingen:

- `allowed`
- `denied`
- `waiting_for_secret`
- `waiting_for_approval`

## Regels

1. Unknown tools zijn geblokkeerd.
2. `candidate` en `reviewed` tools voeren niets uit.
3. `approved_readonly` mag alleen expliciete read scopes zonder approval.
4. `approved_write_gated` mag read scopes zonder approval, maar write/install/connect/cost/resource-heavy acties alleen met consumed approval-id.
5. Raw secret reads zijn altijd verboden.
6. Missing env keys geven `waiting_for_secret`; de UI toont alleen present/missing.
7. Elke check schrijft redacted audit metadata en `tool_permission_checks`.
8. De registry is geen executor. Een latere MCP/tool runner moet verplicht eerst deze check gebruiken.

## Candidate scoring

Kandidaten krijgen een manifest-only triage score van 0 tot 100. Dit is geen bewijs dat een GitHub-repo actueel, veilig of geschikt is. Het is alleen een manier om efficiënter te kiezen welke bestaande projecten eerst een echte review krijgen.

Criteria:

- product fit;
- reuse leverage;
- permission safety;
- maintenance confidence;
- cost efficiency;
- resource fit;
- integration complexity;
- replaceability.

Zonder actuele repo-scan blijft `evidence_level` `manifest_only`. De standaard next action is daarom altijd `verify_current_repo_status`.

### GitHub metadata refresh

Read-only refresh is beschikbaar via:

- dashboardknop `Refresh GitHub metadata`;
- `POST /api/tool-registry/github-refresh`;
- `scripts/leon-refresh-github-candidates`.

Scope:

- alleen publieke `https://api.github.com/repos/{owner}/{repo}` requests;
- geen token, OAuth, accountkoppeling, clone, install, package download of write;
- batch is begrensd en sequentieel;
- rate-limit stopt de batch zacht en laat bestaande manifesten bruikbaar.

Opgeslagen metadata is allowlisted:

- repo-identiteit: `full_name`, `owner_login`, `repo_name`, `html_url`, `source_api_url`;
- projectmetadata: description, homepage, topics, language, default branch, license;
- onderhoud/adoptie: stars, forks, open issues, archived/disabled/fork/template, pushed/updated/created dates;
- refresh bookkeeping: `fetched_at`, `etag`, `refresh_status`, bounded rate-limit headers.

Niet opgeslagen:

- README/body-content;
- issue/PR titels;
- commit messages;
- contributors, e-mails of raw owner object;
- raw API responses;
- cookies, tokens, request env, local paths.

Een succesvolle refresh verhoogt alleen het bewijsniveau naar `github_metadata` en beïnvloedt maintenance/adoption criteria. Het promoveert nooit automatisch naar `approved_readonly` of `approved_write_gated`.

Mogelijke aanbevelingen:

- `evaluate_for_readonly_review`
- `sandbox_review`
- `keep_candidate_research`
- `deprioritize_or_replace`
- `deprioritize_or_reject`

High-risk, write-capable, install/connect/resource-heavy of secret-adjacent tools krijgen automatisch extra next actions zoals security review en approval vóór uitvoering.

## Adoption shortlist

De adoption shortlist is een advieslaag naast manifeststatus. De shortlist wijzigt nooit `status`, geeft geen approval en voert niets uit.

Lanes:

- `evaluate_now`: hoge score, live GitHub metadata, low/medium risk, geen write scopes of external effects.
- `sandbox_later`: nuttig, maar eerst sandboxplan nodig door MCP/tool-complexiteit, env keys, write scopes, external effects of lagere zekerheid.
- `hold`: wachten op hardware, productfase, extra security review, metadata of resourcebesluit.
- `reject`: niet adopteren zonder expliciete override, bijvoorbeeld rejected/critical/archived/stale/blockers.

Elke shortlist-card toont:

- manifeststatus blijft unchanged;
- no approval granted;
- read/write scopes;
- env key namen zonder waarden;
- approval-required acties;
- allowed-without-approval acties;
- forbidden actions;
- sandbox requirement;
- blockers en next actions.

Een candidate in `evaluate_now` is dus alleen “eerst reviewen”, niet “installeren” of “goedkeuren”.

## Review packets

Voor `evaluate_now` kandidaten maakt Leon review-packets. Een review-packet is geen approval en geen statuswijziging.

Packet policy:

- `review_status = needs_review`;
- `execution_allowed = false`;
- `no_approval_granted = true`;
- `status_unchanged = true`;
- scope is alleen `read_only_fit_security_license_review`.

Een packet moet fit/security/license/scope/install-plan beoordelen:

- productfit tegen het Leon-plan;
- licentie en onderhoud;
- security surface;
- exacte read/write/env scopes;
- minimale sandboxaanpak;
- rollback;
- keuze: hergebruiken, sandbox eerst, later vasthouden of custom/alternatief bouwen.

Niet toegestaan in review-packets:

- installeren;
- account koppelen;
- approval maken of consumeren;
- manifeststatus promoten;
- externe write uitvoeren;
- resource-heavy werk starten;
- secretwaarden tonen.

De knop/actie voor review-taken maakt alleen lokale planned taken aan. Ook dat geeft geen toestemming voor uitvoering.

## Dashboardgedrag

Het dashboard toont:

- geregistreerde tool manifests;
- source URLs voor GitHub/MCP kandidaten;
- triage score, aanbeveling, bewijsniveau en next actions;
- adoption lane en gates;
- read/write scopes;
- vereiste env keys zonder waarden;
- recente permission checks;
- reden waarom acties toegestaan of geblokkeerd zijn.

Done-taken worden standaard verborgen uit de backlogweergave, maar blijven in state en audit beschikbaar.
