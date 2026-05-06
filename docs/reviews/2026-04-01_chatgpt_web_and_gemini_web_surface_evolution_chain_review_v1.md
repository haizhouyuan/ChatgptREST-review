# 2026-04-01 chatgpt_web.ask / gemini_web.ask Surface Evolution Chain Review v1

## 1. Scope

This review is a read-only investigation of how `chatgpt_web.ask` / `gemini_web.ask` evolved inside ChatgptREST:

- from standalone low-level MCP / `/v1/jobs` ask paths
- through wrapper / CLI layers
- into advisor routes
- then into `/v3/agent/turn`
- and finally into the slim public advisor-agent MCP

The goal is to answer four concrete questions:

1. What entrypoints and middle layers exist now
2. Which layers are historical accretion and the source of confusion
3. Which layers are actually live/current versus compatibility or maintenance-only
4. What code and document evidence proves each conclusion

## 2. Executive Verdict

### 2.1 Short answer

`chatgpt_web.ask` and `gemini_web.ask` are no longer the intended user-facing northbound entrypoints for coding agents.

They now sit in the **execution substrate** under several higher layers:

1. low-level `/v1/jobs kind=*web.ask`
2. legacy broad/admin MCP tools
3. legacy/provider-first wrapper + jobs CLI path
4. advisor routes (`/v2/advisor/ask`, older `/v1/advisor/advise`)
5. current public agent facade (`/v3/agent/turn`)
6. current public advisor-agent MCP (`advisor_agent_turn/status/cancel/wait`)

The repository looks messy because these layers were added **additively**, not by retiring prior surfaces. The result is that old and new abstractions coexist:

- low-level job kinds still exist
- broad MCP still exists
- old advisor surfaces still exist
- new public agent facade exists
- the wrapper and CLI can still reach both worlds

### 2.2 What is canonical now

For coding agents, the canonical path is:

`public advisor-agent MCP -> /v3/agent/turn -> internal route/controller/consult/direct-job lanes -> chatgpt_web.ask or gemini_web.ask when needed`

This is explicitly frozen in current repo policy and runtime guards, not just in prose.

### 2.3 What still exists but should be read as non-default

The following are still real, but they are no longer the default northbound surface for coding agents:

- direct `/v1/jobs kind=chatgpt_web.ask|gemini_web.ask`
- broad/admin MCP `chatgptrest-mcp`
- legacy bare MCP tools such as `chatgptrest_ask` / `chatgptrest_consult`
- provider-first wrapper mode
- direct `/v3/agent/*` REST for normal coding-agent identities

## 3. Current Layer Map

## 3.1 Execution substrate

These are the actual provider execution kinds:

- `chatgpt_web.ask`
- `gemini_web.ask`

They are first-class provider kinds in the registry and preset validation layer, not historical ghosts.

Evidence:

- [chatgptrest/providers/registry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/providers/registry.py#L51)
- [chatgptrest/providers/registry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/providers/registry.py#L167)
- [chatgptrest/mcp/_providers.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/_providers.py#L5)

Interpretation:

- this is the durable provider/runtime layer
- it is still live and necessary
- but it is no longer the preferred direct user-facing layer

## 3.2 Low-level jobs surface

The oldest stable northbound abstraction is still `/v1/jobs`.

This is where `kind=chatgpt_web.ask` and `kind=gemini_web.ask` are directly created and managed with:

- submit
- wait
- answer
- conversation

Evidence:

- [docs/client_interactions_v3.md](/vol1/1000/projects/ChatgptREST/docs/client_interactions_v3.md#L17)
- [docs/contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md#L157)
- [chatgptrest/api/routes_jobs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_jobs.py#L256)

Current status:

- still live
- still foundational
- still used by workers, admin tools, maintenance, and some internal lanes
- not the canonical coding-agent northbound path anymore

## 3.3 Broad/admin MCP surface

`chatgptrest/mcp/server.py` is the broad MCP surface that accumulated:

- low-level ask/result/followup
- provider-specific submit helpers
- consult
- advisor ask
- and later even `advisor_agent_turn/status/cancel`

This is one of the main sources of confusion because old and new abstractions coexist in the same MCP server.

Evidence:

- legacy advisor MCP tool: [chatgptrest/mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L1961)
- deprecated provider-specific submit tools: [chatgptrest/mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L2061)
- unified low-level ask tool: [chatgptrest/mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3458)
- consult tool: [chatgptrest/mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3774)
- new agent tool also present here: [chatgptrest/mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3909)
- inventory document calling this the 51-tool adapter: [docs/2026-03-17_mcp_and_api_surface_inventory_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_mcp_and_api_surface_inventory_v1.md#L169)

Current status:

- real and live
- but now an internal/admin/debug-heavy MCP surface
- not the recommended default for Codex / Claude Code / Antigravity

## 3.4 Legacy/provider-first wrapper and jobs-oriented CLI

The repo wrapper and CLI historically exposed `provider -> kind/preset -> jobs`.

That means the user mental model stayed close to:

- choose provider
- choose preset
- submit low-level ask

instead of:

- express task intent
- let agent facade route and manage the run

Evidence:

- convergence blueprint explicitly says the wrapper was provider-first and went through `/v1/jobs`: [docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md#L43)
- current wrapper still has provider-to-kind mapping: [skills-src/chatgptrest-call/scripts/chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py#L557)
- current wrapper still supports legacy mode, but only behind `--no-agent --maintenance-legacy-jobs`: [skills-src/chatgptrest-call/scripts/chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py#L1092)
- skill policy explicitly marks legacy jobs mode as maintenance-only: [skills-src/chatgptrest-call/SKILL.md](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/SKILL.md#L82)
- `chatgptrestctl` still exposes full jobs commands: [chatgptrest/cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L1597)

Current status:

- still real
- wrapper agent mode is live and canonical
- wrapper legacy provider-first mode still exists, but only as maintenance/debug/compat
- CLI jobs surface is still real for ops/manual power users

## 3.5 Advisor surfaces

There are two advisor families relevant to this chain:

1. older wrapper-style advisor
2. v2 advisor ask/advise routes

### Older wrapper advisor

Older advisor flows still build low-level jobs from route decisions.

Evidence:

- old route builder still maps route to `chatgpt_web.ask` / `gemini_web.ask`: [chatgptrest/api/routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L1063)
- old orchestrator retry path still re-dispatches child low-level ask kinds: [chatgptrest/api/routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L410)

Interpretation:

- this surface is historically important
- but it is no longer the main northbound story

### Advisor v2 ask

`/v2/advisor/ask` still performs route-to-execution mapping into low-level ask kinds.

Evidence:

- route map still points to `chatgpt_web.ask` across many routes: [chatgptrest/api/routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L52)
- `ControllerEngine.ask(...)` still receives this route map: [chatgptrest/api/routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1954)

Interpretation:

- `/v2/advisor/ask` is still live
- it is still a real smart-execution lane
- but it is not the canonical coding-agent northbound entry anymore

### Advisor v2 advise

`/v2/advisor/advise` belongs more to the advisor/graph plane than to the coding-agent public northbound lane.

Evidence:

- inventory notes `advise` and `ask` are separate HTTP advisor surfaces: [docs/2026-03-17_mcp_and_api_surface_inventory_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_mcp_and_api_surface_inventory_v1.md#L49)
- maintainer entry still defines advisor plane separately from public agent surface: [docs/ops/2026-03-25_agent_maintainer_entry_v1.md](/vol1/1000/projects/ChatgptREST/docs/ops/2026-03-25_agent_maintainer_entry_v1.md#L8)

Current status of advisor family:

- still real
- still in active use in advisor/openmind integrations
- no longer the canonical default northbound for coding agents

## 3.6 Public agent facade

`/v3/agent/turn` is the current public facade that abstracts over jobs/advisor/provider details.

It is where the architecture tried to stop exposing:

- provider selection
- job state machine management
- wait/answer choreography

Evidence:

- convergence blueprint defines `/v3/agent/*` as the canonical public HTTP surface: [docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md#L78)
- actual agent facade route exists: [chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L3184)
- current internal execution splits are explicit:
  - `consult` branch: [chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L3184)
  - direct Gemini lane: [chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L3266)
  - ChatGPT/controller route map: [chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L3366)

Interpretation:

- `/v3/agent/turn` is real and central
- it is not just documentation; it is the actual orchestration facade
- under the hood it still compiles to old execution kinds and consult/direct-job/controller lanes

## 3.7 Public advisor-agent MCP

This is the slim MCP surface intended for coding agents.

It exists precisely because the broad MCP surface became too noisy and too low-level.

Evidence:

- file header states the purpose plainly: [chatgptrest/mcp/agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L1)
- `advisor_agent_turn` posts to `/v3/agent/turn`: [chatgptrest/mcp/agent_mcp.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/agent_mcp.py#L944)
- coding-agent MCP surface policy freezes this as canonical: [docs/2026-03-23_coding_agent_mcp_surface_policy_v4.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-23_coding_agent_mcp_surface_policy_v4.md#L10)
- `AGENTS.md` freezes the same rule: [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md#L100)

Current status:

- real
- live
- canonical coding-agent northbound surface

## 3.8 OpenClaw compatibility alias

Historically, OpenClaw `openmind-advisor` was part of the fragmentation because it had `advise` / `ask` dual behavior and could also do its own `/wait` + `/answer` choreography.

Evidence for that historical state:

- convergence blueprint records the old dual-backend contract and explicit `/wait` + `/answer` choreography: [docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md#L39)

Current code reality is simpler:

- the OpenClaw plugin still keeps the compatibility tool name `openmind_advisor_ask`
- but it now calls `/v3/agent/turn` directly

Evidence:

- tool description says it calls public `/v3/agent/turn`: [openclaw_extensions/openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L360)
- actual POST target is `/v3/agent/turn`: [openclaw_extensions/openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L442)

Interpretation:

- the compatibility name remains
- the old backend split has been mostly collapsed in code
- this is one example where historical docs describe a messier stage than current code

## 4. Where the Confusion Actually Comes From

The confusion is not just “too many docs”. It is structural.

### 4.1 Additive migration instead of retirement

The convergence blueprint explicitly chose additive migration:

- keep low-level tools
- keep old REST
- add new facade
- migrate clients gradually

Evidence:

- [docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md#L72)

This reduced breakage, but it also means the repo keeps multiple simultaneously valid layers.

### 4.2 Broad MCP contains both old and new worlds

`chatgptrest/mcp/server.py` still exposes:

- legacy provider-level tools
- result/wait tools
- consult
- advisor ask
- new `advisor_agent_turn`

That means one surface itself contains multiple generations of abstraction.

Evidence:

- [chatgptrest/mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3458)
- [chatgptrest/mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3774)
- [chatgptrest/mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L3909)

### 4.3 Wrapper and CLI are dual-track

Both wrapper and CLI were not deleted when public agent mode became canonical.

Instead, they were retrofitted:

- agent/public-MCP by default
- legacy jobs mode still present behind explicit maintenance/debug switches

Evidence:

- wrapper default/legacy split: [skills-src/chatgptrest-call/scripts/chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py#L1092)
- CLI default-to-public-MCP with direct-rest maintenance override: [chatgptrest/cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L1694), [chatgptrest/cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L800)

### 4.4 Advisor and public agent both still route into the same provider kinds

`/v2/advisor/ask` and `/v3/agent/turn` both still map many routes to `chatgpt_web.ask`.

So even when the outer surface changed, the underlying provider execution path often stayed the same.

Evidence:

- advisor route map: [chatgptrest/api/routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L52)
- agent route map: [chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L3366)

This is why it feels like “everything changed but also nothing changed”.

## 5. What Is Real Now vs Compatibility/Legacy

## 5.1 Real and canonical now

For coding agents:

- public advisor-agent MCP at `http://127.0.0.1:18712/mcp`
- `advisor_agent_turn/status/cancel/wait`
- `/v3/agent/turn` as the underlying public facade

Evidence:

- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md#L100)
- [docs/2026-03-23_coding_agent_mcp_surface_policy_v4.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-23_coding_agent_mcp_surface_policy_v4.md#L10)
- [docs/runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L523)

## 5.2 Real, but internal/admin/maintenance-oriented

- `/v1/jobs kind=*web.ask`
- broad/admin MCP tools
- `chatgptrestctl jobs ...`
- wrapper `--no-agent --maintenance-legacy-jobs`
- direct `/v3/agent/*` only for maintenance/internal identities

Evidence:

- direct low-level ChatGPT ask blocked by default: [chatgptrest/api/write_guards.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/write_guards.py#L249)
- coding-agent low-level Gemini/Qwen ask blocked by default: [chatgptrest/api/write_guards.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/write_guards.py#L291)
- coding-agent direct `/v3/agent/*` REST blocked: [chatgptrest/api/routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L283)
- CLI direct `/v3/agent/*` path requires maintenance override: [chatgptrest/cli.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cli.py#L1720)

## 5.3 Real, but no longer the preferred coding-agent northbound

- `/v2/advisor/ask`
- `/v2/advisor/advise`
- older advisor wrapper surfaces

These still matter inside the advisor/OpenMind plane and some integrations, but they are not the coding-agent default entry anymore.

Evidence:

- [docs/ops/2026-03-25_agent_maintainer_entry_v1.md](/vol1/1000/projects/ChatgptREST/docs/ops/2026-03-25_agent_maintainer_entry_v1.md#L43)
- [docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md#L14)

## 5.4 Compatibility aliases / legacy names still present

- `openmind_advisor_ask` tool name in OpenClaw
- legacy bare MCP names such as `chatgptrest_ask`, `chatgptrest_consult`
- deprecated provider-specific submit helpers such as `chatgptrest_chatgpt_ask_submit`

These names still exist because the repo chose gradual migration rather than hard removal.

Evidence:

- compatibility tool name retained in OpenClaw plugin: [openclaw_extensions/openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L360)
- legacy bare MCP names explicitly discouraged in the skill: [skills-src/chatgptrest-call/SKILL.md](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/SKILL.md#L48)
- deprecated submit helpers in MCP server: [chatgptrest/mcp/server.py](/vol1/1000/projects/ChatgptREST/chatgptrest/mcp/server.py#L2061)

## 6. Practical Reading of the Evolution Chain

Chronology from code/doc history:

1. **Low-level provider/job era**
   - `chatgpt_web.ask` existed as a first-class `/v1/jobs` kind
   - Gemini low-level ask was added later as another provider kind
   - evidence in git history: `2025-12-30 d8d794e3 feat: add gemini_web.ask via internal driver`

2. **Broad MCP convenience era**
   - repo exposed many low-level MCP tools and provider-specific submit helpers
   - later unified bare tool `chatgptrest_ask`
   - evidence in git history: `2026-03-02 84fc4d0b feat: L0 core tools + modularization — agent-optimized MCP interface`

3. **Advisor routing era**
   - first-class advisor REST and MCP entrypoints appeared
   - `/v2/advisor/ask` unified smart routing to low-level ask kinds
   - evidence in git history:
     - `2026-02-24 058d1300 feat(advisor): add first-class REST and MCP advisor entrypoints`
     - `2026-03-03 59c8f612 feat: unified advisor_ask MCP tool + /v2/advisor/ask endpoint`

4. **Convergence planning + public facade creation**
   - repo explicitly documented entry fragmentation
   - then added `/v3/agent/*`, public MCP tools, CLI agent commands, and agent-first wrapper defaults
   - evidence in git history:
     - `2026-03-17 b01b4ae2 docs: add advisor agent surface convergence plan`
     - `2026-03-17 67a3fe9d feat(agent): add v3/agent public facade routes`
     - `2026-03-17 44241650 feat(mcp): add public agent MCP tools`
     - `2026-03-17 7a89a3aa feat(cli): add chatgptrest agent turn|status|cancel commands`
     - `2026-03-17 c1149079 feat(call): make chatgptrest_call.py agent-first by default`

5. **Policy hard cutover**
   - public advisor-agent MCP became the canonical northbound surface
   - direct `/v3/agent/*` REST for normal coding-agent identities was blocked
   - wrapper legacy jobs mode became maintenance-only
   - evidence in git history:
     - `2026-03-23 19f30855 feat: default agent cli to public mcp`
     - `2026-03-23 5b253efa feat: block coding-agent direct agent rest`
     - `2026-03-25 78454e94 policy: gate legacy wrapper jobs for maintenance only`

## 7. Final Judgment

The current architecture is not random, but it is layered in a way that still exposes prior generations of abstraction.

The cleanest way to read it is:

- `chatgpt_web.ask / gemini_web.ask` are the durable execution substrate
- `jobs` and broad MCP are the older/public-then-admin surfaces
- `advisor` added a smarter routing layer on top of those kinds
- `/v3/agent/turn` added the current high-level public facade
- `public advisor-agent MCP` is the current coding-agent default northbound

So the problem is not that the repository “forgot” what it is doing. The problem is that it kept too many historical entrypoints alive at once, and only partially demoted them.

That is why the same capability can still be reached through:

- low-level kind
- broad MCP
- wrapper legacy mode
- CLI jobs
- advisor ask
- v3 agent facade
- public MCP
- OpenClaw compatibility alias

The present codebase therefore has a **real canonical path**, but also a **large compatibility shadow**.

That compatibility shadow is the main source of the current “乱七八糟” feeling.
