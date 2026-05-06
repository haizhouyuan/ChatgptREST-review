# 2026-04-01 ChatgptREST Positioning Drift Planning Doc Independent Review v1

## 1. Scope and method

This note is an independent verification pass on:

- `/vol1/1000/projects/planning/docs/2026-04-01_ChatgptREST定位漂移与架构复盘_v1.md`

I also tried to locate the second file name provided in the follow-up request:

- `2026-04-01_ChatgptREST_OpenMind_OpenClaw_边界漂移复盘与平台收口建议_v1.md`

I could not find a file with that name under `/vol1/1000/projects`, including relaxed filename matching on `OpenMind`, `OpenClaw`, `边界漂移复盘`, and `平台收口建议`.

This review does not accept the planning document as authority by itself. Every major conclusion below is checked against at least one of:

- repo history
- live repo layout
- code paths
- maintained docs / ADRs / runbooks

## 2. High-confidence findings

### 2.1 The planning doc is directionally correct on the biggest point

The strongest claim in the planning doc is:

> ChatgptREST is no longer just a REST execution substrate or an OpenClaw/OpenMind plugin backend; it now carries multiple real product/runtime roles.

This is supported.

Evidence:

- early baseline still describes the repo as `REST-first job service (stable contract) + thin MCP adapter for ChatGPT Web automation`
  - `README.md`
  - `pyproject.toml`
  - historical commit `e426742a`
- driver hosting was merged into the repo in `f219cb04`
- current repo layout contains real runtime packages beyond execution:
  - `chatgptrest/advisor`
  - `chatgptrest/controller`
  - `chatgptrest/kernel`
  - `chatgptrest/kb`
  - `chatgptrest/mcp`
  - `chatgptrest/repo_cognition`
  - `chatgptrest/task_runtime`
  - `chatgptrest/workspace`
- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md` explicitly says this is a multi-plane repo, not a single service
- `AGENTS.md` simultaneously describes:
  - REST job queue + worker
  - coding-agent default northbound surface
  - OpenMind v3 advisor system

So on the central question, the planning doc is not hallucinating drift. The drift is real.

### 2.2 The repo identity drift is materially worsened by stale top-level narrative

The planning doc says the repo name/homepage story never upgraded with the code reality. That is correct.

Evidence:

- current `README.md` still opens with `thin MCP adapter`
- current `pyproject.toml` still uses the same description
- those statements are no longer sufficient descriptions of the codebase after:
  - public agent facade
  - public advisor-agent MCP
  - workspace contract/service
  - repo bootstrap / closeout governance
  - task runtime
  - work memory

This is not a wording nit. It causes operator confusion because the canonical top-level story under-describes the actual system.

### 2.3 The repo did not merely “serve OpenClaw plugins”; it also built a separate coding-agent northbound surface

This point is central, and it is strongly supported.

Evidence:

- `AGENTS.md` declares coding-agent default entry as public advisor-agent MCP at `http://127.0.0.1:18712/mcp`
- `docs/2026-03-23_coding_agent_mcp_surface_policy_v4.md` states public advisor-agent MCP is the canonical northbound surface
- the same policy explicitly blocks normal coding-agent identities from directly calling `/v3/agent/*`
- `chatgptrest/api/routes_agent_v3.py` enforces that block in `_DIRECT_AGENT_REST_BLOCKED_CLIENTS`
- `docs/ops/2026-03-25_entrypoint_matrix_v1.md` classifies public MCP as the primary coding-agent entry

This is stronger than “the repo grew a few helper scripts”. It is a deliberate northbound platform decision.

### 2.4 The planning doc is also correct that recent additions are real runtime surface, not docs-only inflation

The doc cites work memory, repo cognition/bootstrap, closeout governance, and task runtime. Those are real code additions.

Evidence:

- repo cognition:
  - `chatgptrest/repo_cognition/bootstrap.py`
  - `chatgptrest/repo_cognition/contracts.py`
  - `chatgptrest/repo_cognition/planes.py`
- bootstrap / closeout entry scripts:
  - `scripts/chatgptrest_bootstrap.py`
  - `scripts/chatgptrest_closeout.py`
- task runtime:
  - `chatgptrest/task_runtime/*`
  - commit series from `b446ce30` through `62e7715d`
- work memory:
  - `chatgptrest/kernel/work_memory_manager.py`
  - `chatgptrest/kernel/work_memory_importer.py`
  - `chatgptrest/cognitive/work_memory_triggers.py`
  - commit series from `5b8c1ff3` through `b9cabbaf`

So the “platformization” claim is backed by code, not just by future-looking documents.

## 3. Where the planning doc is right but needs tighter wording

### 3.1 It says “three-layer platform”, which is useful, but the repo still shows at least two overlapping decomposition schemes

The planning doc proposes:

1. execution substrate
2. OpenMind cognition runtime
3. coding-agent platform

This is a useful freeze candidate.

But the maintained repo docs also use a five-plane operational decomposition:

1. execution
2. public agent surface
3. advisor
4. controller / finbot
5. dashboard

Evidence:

- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md`

My judgment:

- the planning doc is probably right at the product-architecture level
- the maintainer entry is probably right at the operational-ownership level

These are not identical models. That mismatch is one source of confusion. A future freeze must explicitly say whether:

- the 3-layer model is the product architecture
- the 5-plane model is the maintenance taxonomy

Without that clarification, “freeze the architecture” itself will stay ambiguous.

### 3.2 It frames OpenClaw as one important integration, but some March blueprints gave OpenClaw a stronger role than “just one integration”

The planning doc’s mouthpiece is:

> OpenClaw/OpenMind are important integration layers, but no longer the sole top-level narrative.

That is close to right, but it slightly compresses an internal conflict.

Counter-evidence:

- `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md` says:
  - upstream OpenClaw is the shell/runtime/control plane
  - role agents should not become independent product surfaces
- `docs/dev_log/2026-03-12_issue156_personal_assistant_convergence_design_v1.md` says:
  - ChatgptREST should become the only authoritative task plane
  - OpenClaw remains the shell, not the truth source
- `docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md` says:
  - OpenClaw cannot be downgraded to a mere shell
  - ChatgptREST should not be packaged as a future total platform

My judgment:

- the repo did not evolve along one clean line
- there are at least two partially competing March narratives:
  - OpenClaw-primary shell/runtime narrative
  - ChatgptREST public-agent/platform narrative

So the problem is not only “old narrative lagging behind new reality”. It is also that multiple new realities were promoted at different times.

### 3.3 The planning doc treats public agent platform growth as a natural continuation of OpenMind runtime growth, but those were not exactly the same program

The document reads these changes as one drift line. That is understandable, but somewhat too smooth.

Evidence suggests two adjacent but distinct tracks:

- OpenMind / advisor / cognition / task-plane convergence
  - e.g. `docs/dev_log/2026-03-12_issue156_personal_assistant_convergence_design_v1.md`
  - e.g. `docs/integrations/openclaw_cognitive_substrate.md`
- public agent / premium ingress / coding-agent surface convergence
  - e.g. `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md`
  - e.g. `docs/2026-03-18_premium_agent_ingress_and_execution_cabin_blueprint_v2.md`
  - e.g. `docs/2026-03-23_coding_agent_mcp_surface_policy_v4.md`

My judgment:

- they converged in the same repo
- they share code paths in `routes_agent_v3.py`
- but historically they were not one single clean expansion program

That matters because the governance fix is not only “rename the repo story”. It is also “separate the architectural intents that got braided together”.

## 4. Internal contradictions that the planning doc underplays

### 4.1 Plugin backend target drift is real

`docs/integrations/openclaw_cognitive_substrate.md` still documents `openmind-advisor` against:

- `/v2/advisor/ask`
- `/v2/advisor/advise`

But `openclaw_extensions/openmind-advisor/README.md` now says:

- `POST /v3/agent/turn`

This is not a small doc lag. It means the OpenClaw plugin story itself already drifted from advisor v2 surfaces to public agent facade.

### 4.2 “Shells are thin transport adapters” conflicts with how thick `routes_agent_v3.py` has become

`docs/contracts/ADR-002-ingress.md` says shells should be thin transport adapters over domain services.

But `chatgptrest/api/routes_agent_v3.py` now imports and coordinates:

- ask contract normalization
- strategist
- prompt building
- task intake normalization
- advisor runtime
- controller engine
- workspace request/service
- memory capture / work memory triggers
- job store

My judgment:

- the repo still states an adapter-oriented philosophy in some places
- but public agent ingress is already a thick orchestration surface in code

That thick surface may be justified. The issue is that the philosophy and the implementation are now out of sync.

### 4.3 “Do not turn role agents into independent product surfaces” conflicts with “public agent is the default external northbound surface”

One March blueprint warned against role agents becoming independent product surfaces.

But later governance explicitly promotes:

- public advisor-agent MCP as default coding-agent surface
- public agent as the single northbound task entry for external agents and clients

My judgment:

- this is not a fatal contradiction if “public agent” is treated as infrastructure, not persona
- but the repository has not frozen that distinction explicitly enough

## 5. Independent judgment

### 5.1 Your concern is valid

The system is not merely “more capable now”. It is carrying multiple partially overlapping control narratives inside one repo:

- execution substrate
- OpenMind cognition / advisor runtime
- public agent / coding-agent northbound platform
- OpenClaw integration and shell strategy
- controller / maint / finbot / dashboard operational planes

That is why the repo increasingly feels hard to reason about.

### 5.2 The planning doc is mostly right on diagnosis

I agree with the planning document on these core points:

- ChatgptREST has materially drifted from its original identity
- the drift is not accidental clutter only; it reflects real successful capability growth
- the main failure is governance and boundary freeze lag
- forcing the repo back into “just an OpenClaw plugin backend” would be the wrong move

### 5.3 But I would state the root cause more sharply

My independent wording would be:

> ChatgptREST did not drift along one line from plugin backend to platform. It absorbed at least three architecture programs in parallel: execution substrate hardening, OpenMind cognition hosting, and public agent northbound platforming. The repo now feels chaotic because these programs were added additively without one authoritative authority matrix, retirement matrix, or top-level story rewrite.

This is slightly stronger than the planning doc because it identifies not just “identity lag”, but also “parallel architecture programs without final arbitration”.

### 5.4 I would not use “OpenClaw is just one integration” as the freeze sentence

That wording is too weak for the March evidence.

A better freeze sentence is:

> OpenClaw remains a first-class shell/runtime strategy for this ecosystem, but it is no longer the only northbound story that ChatgptREST serves.

That better matches both:

- the OpenClaw shell/control-plane documents
- the public agent default coding-agent ingress documents

## 6. Recommended mouthpiece

If one sentence must be frozen now, I would use:

> ChatgptREST is now the integrated host for execution substrate, OpenMind cognition runtime, and public agent northbound governance. OpenClaw remains a first-class shell/runtime integration, but not the sole product narrative. New work must declare its owning layer and may not enter the repo without an explicit boundary and retirement decision.

## 7. Practical next steps

### P0

1. Freeze one authority matrix:
   - execution
   - cognition
   - northbound agent surface
   - shell/runtime integration
   - maintenance/control
2. Freeze one retirement matrix:
   - `/v1/jobs`
   - `/v2/advisor/*`
   - `/v3/agent/*`
   - public MCP
   - OpenClaw plugins
3. Rewrite top-level repo mouthpieces:
   - `README.md`
   - `pyproject.toml`
   - `AGENTS.md`

### P1

1. Explicitly reconcile the 3-layer and 5-plane models
2. Mark `docs/integrations/openclaw_cognitive_substrate.md` as historical or revise it to current plugin backend reality
3. Add one architecture ADR that answers:
   - what is core
   - what is integration
   - what is northbound default
   - what is maintenance-only

## 8. Final conclusion

The planning doc is strong and mostly correct. I would accept it as a draft diagnosis, not yet as the final frozen mouthpiece.

The main reason is not lack of evidence. The main reason is that the repo shows a deeper conflict than the doc fully says:

- not only old identity vs new reality
- but also multiple new realities promoted by different March architecture programs

So my independent answer is:

**Yes, ChatgptREST has become structurally too mixed, and your concern is justified. The fix is not rollback. The fix is a hard architectural arbitration pass with an authority matrix and retirement matrix, because the repo is currently hosting several partially overlapping “centers of gravity” at once.**
