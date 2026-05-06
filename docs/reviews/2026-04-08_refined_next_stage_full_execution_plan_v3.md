# Refined Next-Stage Full Execution Plan V3

Date: 2026-04-08

Supersedes:

- [Refined Next-Stage Full Execution Plan V2](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v2.md)

Related correction records:

- [Final Stage Comparison And Gap Assessment V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_final_stage_comparison_and_gap_assessment_v1.md)
- [Residual Gap And Risk Note V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_residual_gap_and_risk_note_v1.md)

## 1. Why V3 exists

V2 was completed successfully as a boundary-consolidation release.

After red-team review, four follow-on items need to be made explicit so the next wave does not drift:

1. the platform now has both `advisor_agent_*` and `coding_agent_*` public contracts, so the old advisor lane needs an explicit lifecycle decision
2. the current unified release gate pack is strong on contract and harness evidence, but it still lacks one live Deep Research finality gate
3. `scope_project` backfill tooling exists, but live write-back must remain blocked until the data audit is rerun and explicitly signed off
4. promotion now has inventory and maintenance harnesses, but the root cause of low active coverage still needs a dedicated diagnosis pass

V3 keeps the completed stage intact and defines the next concrete realignment wave.

## 2. Facts corrected by code inspection

These are now treated as current facts:

1. `engine.py` is already completion-contract-aware at current HEAD.
2. `advisor_agent_status` / `advisor_agent_wait` already receive completion-contract fields through the `/v3/agent/session` projection path.
3. the real unresolved problem is not “missing contract projection” anymore.
4. the real unresolved problem is **surface governance**:
   - what remains default
   - what remains compatibility
   - what becomes deprecated later

## 3. Next-wave objective

The next wave is a **surface-clarification and live-finality hardening wave**.

Its purpose is:

> keep the newly-correct boundary shape, while removing ambiguity around public lanes and adding one harder live finality proof.

This wave is narrower than a full platform rewrite.

## 4. Required outcomes

### 4.1 Public-lane governance outcome

By the end of this wave, the repo must state clearly:

- whether `advisor_agent_*` remains:
  - long-term compatibility surface
  - temporary compatibility surface with deprecation path
  - broad product surface not intended for mature coding agents

And the docs must explicitly say:

- `coding_agent_*` is the default lane for mature coding agents
- `advisor_agent_*` is not the default coding-agent lane

### 4.2 Live finality proof outcome

The release discipline must include one **live Deep Research finality gate** that proves:

1. a provisional result does **not** claim `answer_ready=true`
2. a final result does produce:
   - `answer_state=final`
   - canonical answer retrieval
   - stable public completion semantics

### 4.3 Data-write safety outcome

No live `scope_project` backfill may run unless:

1. the current data audit is rerun
2. mismatch/orphan/noisy-project conditions are reviewed
3. the run is explicitly marked safe or conditionally safe

### 4.4 Promotion diagnosis outcome

The repo must produce a dedicated diagnosis record that distinguishes:

- gate strictness
- missing scheduling
- absent promotion invocation
- source quality issues

This must exist before any future throughput or “active ratio” program is approved.

## 5. Work packages for V3

This wave is executed as four work packages.

### Work package G: Public-lane lifecycle decision

#### Objective

Freeze the relationship between:

- `coding_agent_*`
- `advisor_agent_*`
- internal broad MCP surfaces

#### Required outputs

1. one decision document defining:
   - default lane
   - compatibility lane
   - non-default broad lane
2. updates to:
   - `AGENTS.md`
   - relevant wrapper/skill docs
   - contract wording where needed

#### Acceptance

1. A new maintainer can tell which lane is default for coding agents without inferring from code.
2. The docs make clear whether `advisor_agent_*` is compatibility-only or broad product-facing.
3. No doc claims both lanes are the default coding-agent path.

### Work package H: Live Deep Research finality gate

#### Objective

Add one live gate that verifies finality semantics, not just contract projection.

#### Required outputs

1. one live gate runner
2. one artifact pack with:
   - provisional vs final evidence
   - `answer_ready` behavior
   - canonical answer retrieval behavior
3. one review packet explaining how to interpret green vs red

#### Acceptance

1. The gate proves that provisional does not masquerade as final.
2. The gate proves that final can be retrieved through the supported public path.
3. The gate writes machine-rerunnable artifacts.

### Work package I: `scope_project` live-backfill precondition pack

#### Objective

Turn the existing audit and backfill tooling into an explicit precondition contract for any future live write.

#### Required outputs

1. rerun of scope-project audit
2. one backfill readiness note:
   - safe
   - conditional
   - blocked
3. one execution note stating whether live write is approved or deferred

#### Acceptance

1. No one needs to guess whether the backfill script is safe to run.
2. The decision is based on current DB evidence, not the old preflight snapshot alone.
3. If blocked, the blocking reasons are enumerated.

### Work package J: Promotion root-cause diagnosis

#### Objective

Produce a root-cause diagnosis for low active coverage.

#### Required outputs

1. one diagnosis report
2. one supporting evidence bundle:
   - inventory
   - audit counts
   - scheduling / invocation evidence
   - age distribution or equivalent backlog evidence

#### Acceptance

1. The diagnosis identifies the dominant cause with evidence.
2. It separates “maintenance harness exists” from “promotion is healthy”.
3. It does not jump directly into throughput tuning without first proving the root cause.

## 6. Explicit non-goals for V3

This wave does **not** include:

- broad new substrate expansion
- another generic advisor-semantic expansion
- bulk document cleanup
- broad promotion optimization rollout
- replacing the unified release gate pack

## 7. Exit condition for V3

This wave is complete when:

1. public-lane governance is explicit
2. one live Deep Research finality gate is green
3. `scope_project` live-write readiness is explicitly decided
4. promotion low-active root cause is explicitly diagnosed

At that point, the next problem will no longer be “what is the correct public shape?” but “what long-tail simplification and governance hardening should be prioritized next?”
