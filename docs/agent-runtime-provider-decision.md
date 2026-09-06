# Leon AI Assistant — agent runtime provider decision

Status: decision record  
Decision date: 2026-08-01  
Decision: use OpenAI Agents SDK for Python as the first real agent adapter target, behind Leon's existing gates.

## Decision

Keep `local_mock` as the only active runtime for now. For the first real model-backed runtime, target OpenAI Agents SDK for Python.

No framework is installed in this slice. Real provider execution remains blocked until the provider adapter is implemented behind:

- `agent_assignment_proposals`;
- task packets;
- model routing;
- audit events;
- approval gates;
- secret redaction;
- capability-scoped tools.

## Why OpenAI Agents SDK first

- The project is currently Python and local-first.
- The user already wants OpenAI/Codex as the cloud route for tool-making and coding.
- The SDK is lightweight enough to wrap behind the current dashboard/task/audit model.
- It can cover the early Personal Agent, Research Agent, code review and tool-calling paths before Leon needs a heavier workflow engine.

## Alternatives

| Option | Decision | Reason |
|---|---|---|
| OpenAI Agents SDK Python | Primary first real adapter | Best fit for Python codebase, OpenAI key flow and small wrapper surface. |
| LangGraph | Reserve | Strong for stateful/durable graph workflows; likely useful later for Night Queue or complex human-in-loop flows. |
| Pydantic AI | Reserve | Strong typed outputs/dependencies; useful for component agents if strict schemas become the main pain. |
| VoltAgent | Defer | Interesting TypeScript platform/observability stack, but adds stack complexity before Leon's core gates are mature. |

## Adapter gate

The first real provider adapter must not bypass the existing local governance.

Required:

- starts only from an applied `agent_assignment_proposal`;
- writes `provider_call_started` and `provider_call_completed_or_failed` audit events;
- redacts prompt/tool secrets before persistence;
- returns reviewable evidence;
- uses dynamic model routing;
- fails into `waiting_for_secret`, `waiting_for_approval`, `waiting_for_user` or `blocked` instead of improvising;
- cannot perform external writes without a consumed approval id.

Forbidden until later explicit approval:

- reading raw `.env.local` inside agent context;
- installing packages from a task;
- shell commands;
- filesystem writes;
- account connections;
- mail/calendar/payment/server/browser writes;
- GPU model downloads or heavy jobs.

## Sources checked

- OpenAI Agents SDK guide: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents SDK Python docs: https://openai.github.io/openai-agents-python/
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph workflows/agents: https://docs.langchain.com/oss/python/langgraph/workflows-agents
- Pydantic AI docs: https://pydantic.dev/docs/ai/overview/
- VoltAgent docs: https://voltagent.dev/docs/

## Next implementation slice

Implement a disabled-by-default `openai_agents_sdk_python` provider adapter shell:

1. validate `OPENAI_API_KEY` presence without exposing value;
2. convert Leon task packet to provider input;
3. produce a dry-run provider call plan;
4. block actual provider calls until an explicit provider-enable approval exists.
