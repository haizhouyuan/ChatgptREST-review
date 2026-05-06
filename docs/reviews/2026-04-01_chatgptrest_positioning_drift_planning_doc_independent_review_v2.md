# 2026-04-01 ChatgptREST Positioning Drift Planning Doc Independent Review v2

## 1. Why v2 exists

`v1` reviewed only the planning-repo document:

- `/vol1/1000/projects/planning/docs/2026-04-01_ChatgptREST定位漂移与架构复盘_v1.md`

After that review, a second relevant document was located in the maint repo:

- `/vol1/maint/docs/2026-04-01_ChatgptREST_OpenMind_OpenClaw_边界漂移复盘与平台收口建议_v1.md`

This `v2` updates the independent judgment after reading both documents and re-checking the strongest claims against:

- ChatgptREST repo history
- current code surfaces
- OpenClaw-side usage docs
- client registry
- current worktree state

## 2. Evidence weight of the two documents

The two documents should not be given equal evidentiary weight.

### Planning doc

- file exists in the planning repo
- content is coherent with repo history and March architecture documents
- useful as a structured diagnosis draft

### Maint doc

- file exists at `/vol1/maint/docs/...`
- but is currently **untracked** in the maint repo
- `git -C /vol1/maint status --short` reports it as `??`
- `git -C /vol1/maint log --all -- <file>` returns no history

My judgment:

- the maint doc is useful as a live operator diagnosis
- but it is not yet a frozen authority artifact
- it should be treated as a strong memo, not as an already-ratified architectural mouthpiece

## 3. What the maint doc gets right

### 3.1 It correctly sharpens the “platform drift” diagnosis

The maint doc says the real issue is not “ChatgptREST became independent”, but that:

- system fact moved toward a shared control plane
- while names, repos, docs, and client mental models stayed in an older era

This is directionally correct and better phrased than a simplistic “plugin backend drift” story.

Why it is supported:

- `chatgptrest/api/app.py` mounts far more than jobs:
  - jobs
  - advisor
  - consult
  - issues
  - metrics
  - ops
  - evomap
  - cognitive
  - dashboard
  - advisor v3
  - agent v3
  - task runtime
- `AGENTS.md` mixes execution substrate, coding-agent entry, and OpenMind advisor runtime in one maintainer surface
- the public advisor-agent MCP is now the default coding-agent entry
- `client_projects_registry.md` shows multiple external client repos already consume ChatgptREST as a shared service surface

### 3.2 It is right that OpenClaw usage has been narrowed on the ChatgptREST side

The maint doc says OpenClaw has been operationally pushed into a client position.

This is partly supported if read carefully.

Evidence:

- `/vol1/1000/projects/openclaw/docs/chatgptREST.md` says:
  - OpenClaw coding-agent model turns should default to public advisor-agent MCP
  - OpenClaw should not keep a parallel low-level `kind=*web.ask` lane
  - `openclaw-wrapper` low-level identity is intentionally disabled
- `docs/client_projects_registry.md` registers `openclaw` as one consumer project among several
- `docs/2026-03-23_coding_agent_mcp_surface_policy_v4.md` and `AGENTS.md` make coding-agent usage MCP-first and low-level ask non-default

So from the **ChatgptREST integration-governance** angle, OpenClaw is indeed treated more like a client than a system-defining ingress owner.

### 3.3 It is right that live repo hygiene amplifies the “everything is drifting” feeling

This is also supported.

Current repo state shows:

- main worktree is dirty
- branch is ahead and behind upstream
- many historical worktrees still exist
- many `/tmp/...` worktrees are `prunable`
- multiple long-lived and temporary worktree families coexist

This does not create the conceptual drift by itself, but it makes the repo feel less governable and makes boundary confusion harder to resolve.

## 4. Where the maint doc overstates things

### 4.1 “ChatgptREST = shared AI control plane runtime” is a strong candidate freeze, not yet fully frozen fact

I agree this is probably the most useful short-term mouthpiece.

But I would not present it as already-settled repo truth.

Why:

- `README.md` still describes ChatgptREST as `REST-first job service + thin MCP adapter`
- `pyproject.toml` still repeats the same
- `AGENTS.md` still opens from the job-queue/worker story, then later introduces OpenMind v3 and coding-agent entry
- several March docs still present different system centers of gravity

My judgment:

- “shared AI control plane runtime” is the best proposed freeze sentence
- but it is currently a proposed arbitration result, not a universally aligned repository fact

### 4.2 “OpenClaw is now just a client” is too absolute

This is the maint doc’s sharpest overreach.

There is good evidence that OpenClaw has been reduced to a **client role with respect to ChatgptREST’s northbound policy**.

But there is also strong counter-evidence that OpenClaw remains a first-class shell/runtime strategy in the broader architecture:

- `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md`
  - upstream OpenClaw is the shell/runtime/control plane
- `docs/dev_log/2026-03-12_issue156_personal_assistant_convergence_design_v1.md`
  - OpenClaw remains the shell, not the truth source
- `docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md`
  - OpenClaw cannot be downgraded to a mere shell

My judgment:

- OpenClaw is no longer the only top-level narrative
- OpenClaw is no longer allowed to define ChatgptREST’s product boundary
- but OpenClaw is still more than “just another client” in the whole-system design

The accurate wording is:

> OpenClaw is now a first-class shell/runtime integration that consumes ChatgptREST as a shared backend, rather than the sole product-defining owner of that backend.

### 4.3 The worktree mess is an amplifier, not the root cause

The maint doc correctly notes dirty main + stale worktrees + rollout residue.

But the boundary problem existed before this current repo state.

The conceptual drift is already visible in committed March artifacts:

- substrate positioning docs
- public agent convergence docs
- premium ingress docs
- maintainer entry / entrypoint matrix docs

So:

- worktree hygiene matters
- but cleaning worktrees alone will not solve the architectural ambiguity

### 4.4 The Anthropic harness comparison is useful, but secondary

The maint doc compares current maturity against Anthropic harness best practice and says the system is still “foundation only”.

That may be broadly fair, but it is not the core evidence line for the boundary question.

My judgment:

- for this particular dispute, local repo history and current surface policy matter more than external benchmark framing
- I would treat the harness comparison as advisory texture, not as decisive evidence

## 5. Updated independent judgment

After reading both documents, my judgment becomes:

### 5.1 The planning doc is the better diagnosis draft

It better captures:

- layered platform drift
- additive growth without boundary freeze
- the need to distinguish execution / cognition / coding-agent platform roles

### 5.2 The maint doc is the better escalation memo

It better captures:

- operator pain
- naming drift severity
- live repo/worktree mess
- the need to stop pretending ChatgptREST is still a narrow backend

### 5.3 Neither document alone is the final mouthpiece

The planning doc is slightly too smooth about the history.

The maint doc is slightly too aggressive about the end-state, especially on:

- `OpenClaw = client`
- `ChatgptREST = already-frozen control plane runtime`

The correct synthesis is between them.

## 6. The synthesis I would freeze

If I were freezing the current truth now, I would use this:

> ChatgptREST has evolved into the integrated host for execution substrate, OpenMind cognition runtime, and shared northbound agent governance. OpenClaw remains a first-class shell/runtime integration on top of that host, but no longer defines its sole product narrative. New work must declare its owning layer and may not enter the repo without an explicit boundary and retirement decision.

This wording does four important things:

1. admits platform reality
2. preserves OpenClaw’s importance
3. avoids pretending the old “plugin backend” story still fits
4. avoids overstating that all repos already agree on one final identity

## 7. Practical implications

### Immediate

1. do not keep teaching `ChatgptREST = thin MCP adapter`
2. do not keep teaching `OpenClaw = owner of ChatgptREST boundary`
3. do not keep teaching multiple default northbound surfaces

### Next architecture step

One ADR should explicitly freeze:

1. product identity
2. layer ownership
3. default northbound surfaces
4. maintenance-only surfaces
5. retirement targets for old surfaces

### Hygiene step

Run a separate cleanup pass for:

- worktree inventory
- prunable residue
- rollout leftovers
- stale branch/worktree mapping docs

But keep that as a separate governance action, not a substitute for architecture arbitration.

## 8. Final answer

The maint doc meaningfully strengthens the case that the repo has outgrown its old identity. It does **not** by itself prove that “OpenClaw is now merely a client” in the full-system architecture, because committed March materials still treat OpenClaw as a first-class shell/runtime layer.

So my updated independent answer is:

**Yes, the boundary problem is real and serious. The best correction is to freeze ChatgptREST as the integrated host/platform, but to describe OpenClaw as a first-class shell/runtime integration rather than flattening it into an ordinary client.**
