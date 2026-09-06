# Runtime and model reuse review

Status: US-007 review complete  
Review date: 2026-08-09  
Scope: Phase 2 Leon Shell, agent flow and model routing reuse decisions. This is not an install plan, approval, provider enablement, model download, GPU run or browser runtime enablement.

## Decision summary

| Area | Candidate | US-007 decision | Why |
| --- | --- | --- | --- |
| Agent runtime | OpenAI Agents SDK for Python | First real agent adapter target, disabled until sandbox gates pass | Fits the Python control plane and provides small agent/runtime primitives that can sit behind Leon approvals, audit, model routing and review. |
| Tesla M40 local backend | llama.cpp | First backend candidate | Best low-level fit for GGUF/quantized models, CPU fallback and explicit GPU/CUDA tuning on old or constrained hardware. |
| Second local backend | Ollama | Second backend candidate | Best operator experience and simple local API, but it hides more runtime details than llama.cpp and still needs M40 driver/backend benchmarks. |
| Gateway/sandbox | LiteLLM | Later sandbox only | Useful for provider abstraction, fallback, budgets and gateway behavior after Leon's own route decisions are stable. Not a core runtime dependency now. |
| Controlled browser work | Playwright MCP / Browser Use | Consider only when browser work is in scope | Both can avoid custom browser automation, but browser state, clicks, form fills, downloads, stealth/proxy features and external writes require separate scope and approval gates. |

## Acceptance criteria mapping

- OpenAI Agents SDK reviewed for agent runtime: covered by `docs/agent-runtime-provider-decision.md`, `docs/openai-agents-sdk-sandbox-plan.md`, `config/agent-runtime-provider.json` and `docs/tool-reuse-review-results.md`.
- llama.cpp reviewed as first Tesla M40 backend candidate: covered by `docs/local-gpu-model-runtime-readiness.md`, `config/model-routing.json` preferred backend order and `llama-cpp-candidate` in `config/tool-catalog.candidates.json`.
- Ollama reviewed as second local backend candidate: covered by `docs/local-gpu-model-runtime-readiness.md`, `config/model-routing.json` preferred backend order and `ollama-candidate` in `config/tool-catalog.candidates.json`.
- LiteLLM considered later for gateway/sandbox usage: covered by `docs/litellm-sandbox-plan.md` and the `LiteLLM` section in `docs/tool-reuse-review-results.md`.
- Playwright MCP / Browser Use considered only if controlled-browser work is in scope: covered by `docs/browser-research-tool-evaluation.md` and the browser candidates in `config/tool-catalog.candidates.json`.

## Source check

Official/current sources checked for this story:

- OpenAI Agents SDK docs: Agents are model-plus-instructions/tools units with optional handoffs, guardrails and structured outputs; `Runner` owns the agent loop; the Python package remains the right first adapter candidate, but Leon must keep its own permission preflight and audit gates ahead of SDK tool execution.
- llama.cpp repo and server docs: llama.cpp supports GGUF/quantized local inference, CUDA, CPU/GPU hybrid use, and a local OpenAI-compatible server. That makes it the first M40 backend candidate because Leon can benchmark and tune the narrow backend surface before wrapping it in model routing.
- Ollama hardware docs: Ollama supports NVIDIA GPUs with compute capability 5.0+ and lists Tesla M40 at 5.2, but requires suitable drivers. It remains the second candidate because it is easier to operate but less explicit for first-pass M40 diagnostics.
- LiteLLM docs: LiteLLM is a gateway/proxy layer for OpenAI-compatible access, routing, fallback, rate limits and budgets. It should be sandboxed later, after Leon route decisions and secret boundaries are stable.
- Playwright MCP repo: Playwright MCP exposes browser automation through accessibility snapshots and has isolated profile options, but its own docs say MCP is not a security boundary. Use only after a controlled-browser scope exists.
- Browser Use repo/docs: Browser Use is strong for complex browser tasks and supports domain constraints, but hosted/cloud capabilities include stealth/proxy/captcha-related features. Those stay forbidden for Leon unless a separate, explicit policy changes.

Source references:

- https://openai.github.io/openai-agents-python/
- https://openai.github.io/openai-agents-python/agents/
- https://openai.github.io/openai-agents-python/running_agents/
- https://github.com/ggml-org/llama.cpp
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://docs.ollama.com/gpu
- https://docs.litellm.ai/
- https://github.com/microsoft/playwright-mcp
- https://github.com/browser-use/browser-use

## Runtime gates

No candidate is promoted by this review.

Required before any runtime enablement:

- explicit approval for installs, API calls, model downloads, browser runtimes or GPU-heavy work;
- pinned dependency/release or source revision;
- disposable sandbox or local-only service binding;
- redacted audit evidence;
- no raw secret exposure to agent prompts, traces, logs or dashboard state;
- rollback plan tested before promotion;
- `local_mock` remains the active agent runtime until a separate provider adapter slice passes.

## Next implementation order

1. Keep `local_mock` active and implement only disabled-by-default adapter shells.
2. If agent runtime work starts, sandbox OpenAI Agents SDK first with a text-only run, then one Leon-preflighted function tool.
3. If local model work starts, validate hardware and driver state, then benchmark llama.cpp before Ollama.
4. Evaluate LiteLLM only after a concrete gateway need appears.
5. Evaluate Playwright MCP or Browser Use only after a concrete controlled-browser workflow is approved.
