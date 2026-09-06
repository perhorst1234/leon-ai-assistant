# Individual MCP server review template

Status: template  
Datum: 2026-08-01  
Beslissing uit catalogusreview: MCP catalogus is read-only bruikbaar; iedere server blijft apart gated.

Gebruik dit template voor elke concrete MCP server voordat Leon die server mag installeren, verbinden of uitvoeren. Dit template is geen approval en geen statuspromotie.

Kort: dit template is geen approval, geen install-toestemming en geen runtime-enable.

## 1. Identiteit

- Servernaam:
- Tool id:
- Bron URL:
- Package/release/commit:
- Maintainer/org:
- Registry entry:
- Laatste release/check datum:
- Reviewer:

## 2. Beslissing

Kies één:

- `reuse_readonly_after_review`
- `sandbox_before_decision`
- `hold_for_later_phase`
- `replace_with_custom_or_alternative`

Motivering:

- Product-fit:
- Waarom reuse beter/slechter is dan custom:
- Welke Leon use-case wordt opgelost:

## 3. Bronnen en provenance

Vereist:

- officiële repo/package;
- exacte commit/release;
- license file;
- security policy;
- changelog/release notes;
- docs voor tools/scopes/config;
- registry metadata indien gebruikt.

Bewijs:

- Repo:
- License:
- Security policy:
- Docs:
- Release:
- Registry:

## 4. License review

- SPDX/license:
- License file pad/URL:
- Enterprise/commercial beperkingen:
- Copyleft/redistribution risico:
- Conclusie:

Gate:

- Bij `NOASSERTION`, ontbrekende license of licentieconflict: niet installeren; eerst manual review.

## 5. Security surface

Classificeer alle surfaces:

- Filesystem read:
- Filesystem write:
- Network read:
- Network write:
- Local process/shell:
- Browser/UI automation:
- OAuth/account connect:
- Cloud/API access:
- Database access:
- Network allowlist/egress policy:
- Personal data:
- Public/external posting:
- Payment/trading/spend:

Risico’s:

- Prompt injection:
- Tool poisoning:
- Confused deputy:
- Credential leakage:
- Supply-chain:
- Maintainer trust:
- Runtime escape:

## 6. Tool schema mapping

Voor elke MCP tool:

| MCP tool | Leon action type | Read scopes | Write scopes | Env keys | External effect | Approval nodig |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

Regels:

- Onbekende tool = deny.
- Write scopes zijn default disabled.
- Tool descriptions en schemas zijn untrusted input.
- Geen wildcard scope tenzij reviewer expliciet motiveert.

## 7. Secret handling

Env-key namen:

- 

Regels:

- Geen raw secret reads.
- Geen secretwaarden in prompts, tool arguments, logs, audit of dashboard API.
- Alleen key-presence/status zichtbaar.
- Secret scope expansion vereist nieuwe approval.

## 8. Sandboxplan

Minimum:

- disposable workspace;
- geen user-home mount;
- geen echte secrets;
- netwerk deny-by-default of expliciet beperkt;
- egress allowlist per server/tool;
- read-only testdata;
- audit logging aan;
- timeout/kill switch;
- rollback klaar.

Sandbox testcases:

- list tools/schema only;
- read-only happy path;
- denied write path;
- denied secret read;
- denied broad filesystem/network path;
- prompt-injection fixture;
- malformed input fixture;
- rollback.

## 9. Approval gates

Install/connect/write/resource-heavy acties vereisen approval-card met:

- action type;
- affected systems;
- exact scopes;
- env keys;
- external effect;
- cost estimate;
- risk level;
- rollback;
- expiry;
- approver.

Geen approval mag worden hergebruikt als:

- target verandert;
- scopes veranderen;
- kosten/destructiviteit/external effect toenemen;
- secret scope verandert;
- versie/release verandert.

## 10. Rollback

Rollback moet bevatten:

- server stoppen;
- manifest status terug naar `candidate` of `rejected`;
- credentials/testkeys intrekken;
- sandbox/workspace verwijderen;
- audit/logs bewaren;
- dashboard taakresultaat vastleggen;
- affected systems controleren.

## 11. Acceptatiecriteria

Een MCP server mag pas verder naar sandbox/approval als:

- identiteit en bron exact gepind zijn;
- licentie handmatig akkoord is;
- alle tools naar Leon scopes gemapt zijn;
- secrets alleen als keynamen zijn geregistreerd;
- read-only testplan bestaat;
- denied-path tests bestaan;
- rollback beschreven is;
- reviewer expliciet beslist heeft;
- audit hash-chain geldig blijft.

## 12. Dashboard taak-uitkomst

De taak `Maak template voor individuele MCP server review` mag op `done` wanneer dit template is vastgelegd en geverifieerd. Het template zelf installeert of keurt geen MCP server goed.
