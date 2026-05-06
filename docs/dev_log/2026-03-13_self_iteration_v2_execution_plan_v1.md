# 2026-03-13 Self-Iteration v2 Execution Plan v1

**Status:** active execution plan  
**Scope:** implement blueprint v2 as bounded mergeable slices, using multi-agent development with central contract control and centralized review/integration.  
**Driver branch:** `codex/self-iteration-v2-impl-20260313`

## 1. Objective

Implement the full `blueprint v2` program without losing control of:

- runtime knowledge visibility,
- execution identity,
- existing actuator behavior,
- outcome collection,
- evaluation calibration,
- promotion/suppression decisions,
- experiment/rollout safety.

This execution plan is intentionally more operational than the blueprint. It is the working memory anchor for the implementation campaign.

## 2. Non-negotiable execution rules

1. Shared contracts are fixed before downstream slices start coding against them.
2. No slice may silently change default runtime behavior unless that slice is explicitly the policy slice being reviewed for that purpose.
3. Every meaningful change must be committed immediately.
4. Every slice must ship with:
   - code
   - focused tests
   - versioned walkthrough
   - explicit acceptance evidence
5. I remain the integration owner:
   - adjudicate contract decisions
   - review all slice outputs
   - run integration and full regression
   - decide merge order

## 3. Delivery model

### 3.1 Why not full parallel from minute zero

The first two slices define shared truth:

- runtime knowledge policy
- execution identity contract

If multiple agents modify downstream behavior before those two are fixed, the likely result is:

- conflicting schema decisions
- duplicated identity logic
- incompatible tests
- wasted implementation effort

So execution starts as **serial foundations**, then expands into **parallel independent slices**.

### 3.2 Multi-agent strategy

**Main integrator (me):**

- Slice A: runtime knowledge policy
- Slice B: execution identity contract
- final review/integration/merge/testing for every slice

**Claude Code parallel lanes after A/B freeze:**

- Lane C: actuator governance
- Lane D: observer-only outcome ledger
- Lane E: evaluator plane seed + HITL scaffolding
- Lane F: immediate noise suppression refinements and test expansion

**Final serial lanes:**

- Slice G: promotion/suppression decision plane
- Slice H: experiment registry + rollout control
- Slice I: bounded proposer

## 4. Global sequence

### Phase 0. Execution setup

Actions:

- create clean implementation worktree/branch
- create this plan document and a live todo anchor
- define slice boundaries, owners, write sets, forbidden files, merge order

Effect:

- implementation campaign has a stable memory anchor
- downstream agents have explicit guardrails

Acceptance:

- plan doc committed
- todo doc committed
- worktree clean after commit

### Phase 1. Foundation contracts (serial)

Actions:

- implement Slice A
- implement Slice B
- freeze contracts in docs and code

Effect:

- downstream slices code against stable visibility and identity rules

Acceptance:

- policy tests pass
- identity tests pass
- no downstream work starts before these contracts are frozen

### Phase 2. Parallel implementation tranche

Actions:

- launch parallel Claude Code lanes for C/D/E/F
- each lane works in isolated branch/worktree
- each lane produces commits + focused tests + walkthrough

Effect:

- development throughput increases without write-set collisions

Acceptance:

- each lane has bounded diff
- each lane passes focused suite
- each lane can be reviewed independently

### Phase 3. Merge and integration tranche

Actions:

- review lane outputs
- merge in dependency order
- resolve cross-slice integration issues
- run expanded regression after each merge tranche

Effect:

- slices become one coherent implementation rather than independent experiments

Acceptance:

- all merged slices share one identity contract and one policy model
- no test regressions introduced during merge

### Phase 4. Final serial tranche

Actions:

- implement G/H/I on top of merged foundations

Effect:

- decision plane, rollout registry, and bounded proposer sit on actual runtime/evaluation truth instead of assumptions

Acceptance:

- promotion/experiment/proposal logic is evidence-gated
- no uncontrolled default mutation

### Phase 5. Full-system validation

Actions:

- run focused slice suites
- run full repo regression
- run replay/integration tests
- run any shadow/guarded live checks required by the new surfaces

Effect:

- final branch is integration-tested, not just slice-tested

Acceptance:

- full regression green
- migration safe
- no hidden behavior changes outside intended slices

## 5. Slice-by-slice implementation table

## Slice A. Runtime Knowledge Policy

**Owner:** main integrator  
**Priority:** P0  
**Can start immediately:** yes

### Target

Make knowledge visibility explicit by path instead of relying on the current implicit `ACTIVE + STAGED` retrieval default.

### Main write set

- `chatgptrest/evomap/knowledge/retrieval.py`
- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/api/routes_consult.py`
- tests for retrieval/context/consult path policy

### Forbidden spillover

- no evaluator logic
- no ledger schema
- no experiment registry

### Actions

1. Add policy abstraction for retrieval path class.
2. Define default policy for:
   - `user_hot_path`
   - `diagnostic_path`
   - `shadow_experiment_path`
   - `promotion_review_path`
3. Enforce path-scoped promotion-status filtering.
4. Emit staged-hit metrics for visibility and later suppression analysis.
5. Add focused tests.
6. Write walkthrough and commit.

### Expected effect

- user-facing hot path stops consuming `STAGED` by default
- diagnostic and shadow paths keep wider visibility where intentional
- later slices no longer need to guess whether staged objects are allowed

### Acceptance

- tests prove `user_hot_path` excludes `STAGED`
- tests prove shadow/diagnostic policy remains distinct
- retrieval telemetry exposes staged visibility stats

## Slice B. Execution Identity Contract

**Owner:** main integrator  
**Priority:** P0  
**Depends on:** A may proceed independently; B should be frozen before downstream ledger/evaluator work lands

### Target

Stabilize identity binding around execution truth:

- `trace_id`
- `run_id`
- `job_id`
- `task_ref`
- `logical_task_id`

### Main write set

- `chatgptrest/telemetry_contract.py`
- `chatgptrest/evomap/knowledge/telemetry.py`
- `chatgptrest/core/advisor_runs.py`
- possibly new helper under `chatgptrest/quality/` or `chatgptrest/core/`
- tests for identity normalization and telemetry binding

### Forbidden spillover

- no runtime decision logic from ledger/evaluator
- no promotion logic

### Actions

1. Define normalized identity contract object/helper.
2. Update retrieval telemetry recording to accept explicit identity inputs.
3. Bridge advisor run lineage into the identity helper.
4. Add `logical_task_id` as explicit future authority field, nullable/derived initially.
5. Record identity confidence / degradation instead of silent fallback.
6. Add focused tests.
7. Write walkthrough and commit.

### Expected effect

- downstream slices can attribute outcomes and evaluations to the same execution chain
- weak `task_ref || task_id` fallback stops being the only linkage mechanism

### Acceptance

- telemetry writes can carry stable identity
- no silent null identity fields in normal path
- replay/idempotency tests pass

## Slice C. Existing Actuator Governance

**Owner:** Claude Code lane  
**Priority:** P1  
**Depends on:** B frozen

### Target

Wrap current self-adjusting runtime actuators with explicit governance.

### Main write set

- `chatgptrest/evomap/actuators/gate_tuner.py`
- `chatgptrest/evomap/actuators/circuit_breaker.py`
- `chatgptrest/evomap/actuators/kb_scorer.py`
- new `chatgptrest/evomap/actuators/registry.py`
- actuator governance tests

### Actions

1. Add actuator metadata contract.
2. Add mode support:
   - `observe_only`
   - `shadow`
   - `canary`
   - `active`
3. Add audit events and last decision linkage.
4. Add rollback trigger and owner fields.
5. Add tests proving observe-only does not mutate runtime defaults.
6. Write walkthrough and commit.

### Expected effect

- current adaptive loops become visible, attributable, and governable

### Acceptance

- each actuator reports governance mode and owner
- observe-only mode is test-proven
- audit trail is emitted for actuator changes

## Slice D. Observer-Only Outcome Ledger

**Owner:** Claude Code lane  
**Priority:** P1  
**Depends on:** B frozen

### Target

Create durable execution outcome rows without influencing runtime behavior.

### Main write set

- new `chatgptrest/quality/outcome_ledger.py`
- new `chatgptrest/quality/schema.py`
- DB migration in `chatgptrest/core/db.py`
- execution closeout integration points
- ledger tests

### Actions

1. Add outcome-ledger schema and migration.
2. Add observer-only writer.
3. Link artifacts and retrieval evidence.
4. Store staged influence, degraded flags, fallback lineage.
5. Add idempotent replay tests.
6. Write walkthrough and commit.

### Expected effect

- the system has one durable place to judge outcomes later

### Acceptance

- high population rate on completed runs in tests
- no runtime behavior change
- replay safe

## Slice E. Evaluator Plane Seed + HITL Scaffolding

**Owner:** Claude Code lane  
**Priority:** P1  
**Depends on:** B frozen; D preferable

### Target

Turn existing QA review capability into a seed evaluator plane, with explicit human calibration scaffolding.

### Main write set

- `chatgptrest/advisor/qa_inspector.py`
- new `chatgptrest/quality/evaluator_service.py`
- new `chatgptrest/quality/human_labels.py`
- evaluator tests

### Actions

1. Define evaluator output schema.
2. Wrap `qa_inspector` as evaluator adapter.
3. Add human label sink.
4. Add disagreement/meta-eval storage contract.
5. Add focused tests.
6. Write walkthrough and commit.

### Expected effect

- model-generated quality judgments stop floating as ad-hoc reports and become structured evaluation records

### Acceptance

- evaluator outputs are structured and versioned
- human override/disagreement path exists
- tests cover parse + storage + disagreement path

## Slice F. Immediate Noise Suppression

**Owner:** Claude Code lane  
**Priority:** P1  
**Depends on:** A frozen; B preferred

### Target

Use existing telemetry (`used_in_answer`, retrieval evidence) to suppress low-value sources safely and early.

### Main write set

- `chatgptrest/evomap/knowledge/retrieval.py`
- `chatgptrest/cognitive/context_service.py`
- maybe consult/retrieval scoring helpers
- suppression tests

### Actions

1. Add suppression scoring hook using used/not-used evidence.
2. Keep it shadow-only first if behavior risk is non-trivial.
3. Measure hit-rate change in tests/fixtures.
4. Add walkthrough and commit.

### Expected effect

- immediate reduction in noisy retrieval influence before larger promotion machinery exists

### Acceptance

- measurable suppression of low-utility sources in tests
- no accidental prompt/route mutation

## Slice G. Knowledge Decision Plane

**Owner:** main integrator after merge tranche  
**Priority:** P2  
**Depends on:** D + E + F merged

### Target

Turn evaluated outcomes into bounded promotion/suppression/revalidation decisions.

### Main write set

- new `chatgptrest/quality/decision_plane.py`
- canonical object decision helpers
- tests

### Actions

1. Add proposal contracts.
2. Add policy gating for promotion.
3. Add shelf-life/revalidation fields.
4. Add walkthrough and commit.

### Expected effect

- “knowledge learning” becomes a governed decision process instead of raw writeback

### Acceptance

- promoted objects require evaluator evidence and freshness policy
- low-value sources can yield suppression decisions

## Slice H. Experiment Registry + Rollout Control

**Owner:** main integrator after G  
**Priority:** P2  
**Depends on:** C + D + E + G merged

### Target

Introduce authoritative experiment and rollout state for candidate improvements.

### Main write set

- new `chatgptrest/quality/experiment_registry.py`
- rollout schema/helpers
- tests

### Actions

1. Add registry schema.
2. Add baseline/candidate association.
3. Add rollback trigger contract.
4. Add shadow/canary status model.
5. Add walkthrough and commit.

### Expected effect

- no adaptive change reaches default behavior without explicit experiment/rollout state

### Acceptance

- experiment state is durable
- rollback requirements are machine-readable
- tests cover state transitions

## Slice I. Bounded Proposer

**Owner:** main integrator after H  
**Priority:** P3  
**Depends on:** G + H merged

### Target

Generate bounded issue/test/proposal outputs from repeated failures without direct unsafe mutation.

### Main write set

- new proposer module(s)
- issue/test proposal templates
- tests

### Actions

1. Map repeated failure tags to allowed proposals.
2. Add proposal serialization.
3. Keep all outputs non-authoritative until reviewed/rolled out.
4. Add walkthrough and commit.

### Expected effect

- repeated failures generate actionable follow-up work, not just logs

### Acceptance

- proposals are evidence-linked
- no direct production mutation path exists

## 6. Multi-agent orchestration plan

### 6.1 Agent launch order

1. Main integrator starts Slice A.
2. Main integrator completes/freeze Slice B.
3. After A/B freeze:
   - launch CC lane C
   - launch CC lane D
   - launch CC lane E
   - launch CC lane F
4. Main integrator reviews and merges C/D/E/F.
5. Main integrator implements G/H/I.

### 6.2 Worktree policy

Each lane gets:

- isolated branch
- isolated worktree
- explicit write set
- explicit forbidden files

### 6.3 Review policy

No lane merges directly.

Review steps per lane:

1. read diff
2. run focused tests
3. run integration sanity where needed
4. run merge-gate tests after landing

## 7. Full validation strategy

### 7.1 Per-slice validation

Each slice must run:

- focused unit tests
- focused integration tests
- `py_compile` where relevant

### 7.2 Merge tranche validation

After merging C/D/E/F:

- run combined focused suites across all landed slices
- verify no identity/policy divergence

### 7.3 Final validation

Before declaring v2 complete:

- full `pytest -q`
- migrations/replay safety checks
- any required guarded live/shadow checks for new runtime governance surfaces

## 8. Merge order

1. A
2. B
3. C / D / E / F in dependency-safe order
4. G
5. H
6. I

## 9. Campaign completion criteria

The campaign is complete only when:

- all slices A-I are landed and integrated
- full repo regression is green
- no hidden default behavior mutation remains outside governance
- versioned walkthrough exists for every slice
- final integration walkthrough and merge handoff are written
