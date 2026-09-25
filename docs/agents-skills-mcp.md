# Agents, skills and MCP

Leon now installs `openai-agents==0.22.2` as its first real agent-runtime SDK
and pins its used MCP surface to `mcp==2.2.0`. Setup verifies all transitive
packages against `requirements.lock` hashes and installs again only when
`pyproject.toml` or that lock changes. Backend and worker start with that virtual
environment; `leon-doctor` reports exact Agents SDK readiness.

Agent behavior starts from validated profiles in `config/agent-skills.json`.
Current profiles include Planner, Research, Manager, Shopper, Server Manager,
3D Model Reference Maker, 3D Printer Manager, Code/Improvement, Review, Memory
and Tool/Connector. Each profile declares task types, allowed actions and output
kind. These profiles do not grant tools, approval, provider calls or file writes.

Shopper has separate validated MCP bindings in
`config/agent-mcp-bindings.json`. Marktplaats, Vinted and AliExpress sources, versions,
commits, artifact hashes, domains, tool allowlists, timeouts and result limits
are fixed there. All three bindings stay `candidate_disabled` while the active
`local_ollama` runtime remains text-only. Even after a binding changes to `readonly`, resolver grants
it only when matching global manifest is `approved_readonly`. Purchase, bid,
payment, messaging, secret reads and anti-bot actions remain hard denied.
Existing assignment, risk, cost and review gates remain authoritative.

`leon-mcp-readonly` is a local stdio MCP server. It exposes exactly three tools:

- `leon_status`: bounded phase, progress and workload counts;
- `list_tasks`: at most twenty redacted task summaries;
- `list_agent_skills`: validated role and capability metadata without prompts.

Every tool declares MCP read-only, non-destructive, idempotent and closed-world
annotations. Server exposes no filesystem, shell, memory-content, secret,
approval or write tool. It opens no port. Test suite negotiates real stdio MCP
session plus in-process session and verifies exact tool inventory.

Example host configuration after `./scripts/leon-setup`:

```json
{
  "mcpServers": {
    "leon-readonly": {
      "command": "/absolute/path/to/leon-ai-assistant/.venv/bin/leon-mcp-readonly",
      "args": ["--db", "/absolute/private/path/control-plane.sqlite"]
    }
  }
}
```

Server requires existing private database, opens SQLite with `mode=ro`, and
never seeds or migrates it. Invocation is trusted-local: caller chooses database
path and already has same operating-system access. Do not commit host paths, credentials or
tokens. Connecting external Gmail, Calendar, GitHub or third-party MCP servers
still needs separate credentials and target-host acceptance. Current Google
Agenda/Gmail connector remains purpose-built read-only code; no broad third-party
MCP server has been silently connected.

Reference implementations:

- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/
- Agents SDK MCP support: https://openai.github.io/openai-agents-python/mcp/
- MCP Python SDK v2: https://py.sdk.modelcontextprotocol.io/
