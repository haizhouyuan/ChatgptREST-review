# Refined Next-Stage Full Execution Plan V6

Date: 2026-04-08

Supersedes:

- [Refined Next-Stage Full Execution Plan V5](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v5.md)

Related records:

- [Productionization Corrective Wave Completion V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_productionization_corrective_wave_completion_v1.md)
- [Productionization Residual Risk Note V1](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_productionization_residual_risk_note_v1.md)
- [Refined Next-Stage Full Execution Plan V4](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-08_refined_next_stage_full_execution_plan_v4.md)

## 1. Why V6 exists

V5 made the `coding-agent-v1` lane production-ready, but it did not finish the platform.

The remaining blockers are no longer architectural ambiguity. They are runtime and governance gaps:

1. the wrapper default surface is now too narrow for broad advisor/planning/review flows, which leaves real user intents failing preflight even though the backend can handle them;
2. the planning knowledge substrate still has extremely low effective runtime reachability:
   - `36,567` planning atoms total
   - `201` active
   - `35,799` staged
   - `36,363` with groundedness `0`
3. the current planning-review maintenance timer is a reviewed-pack maintenance lane, not a general promotion scheduler;
4. KB hybrid search is available in architecture and works under the repo `.venv`, but the platform has not yet frozen the runtime checks and evidence needed to treat it as product-grade recall;
5. targeted regression suites still show wrapper/planning-plane drift and must be restored before a real user acceptance run.

V6 is therefore the first wave whose explicit target is:

> production-grade usable platform behavior, not just a repaired northbound lane.

## 2. V6 objective

V6 is complete only when all of the following are true:

1. the public coding-agent wrapper can route real user requests onto the correct public lane without manual surface tuning;
2. the planning knowledge pipeline has a live, safe, repeatable batch scoring/promotion path rather than a one-off or stale reviewed pack;
3. the planning runtime pack can be refreshed from newly qualified atoms after the batch cycle;
4. KB hybrid search is verified on the actual `.venv` runtime used by services and is captured in evidence;
5. the regression slice around wrapper + planning task plane is green;
6. the resulting state is documented with explicit residual risk and live evidence for the user's upcoming manual test.

## 3. Frozen facts entering V6

These remain true and are not reopened:

1. `coding_agent_*` remains the default mature public coding-agent lane.
2. `advisor_agent_*` remains the broad advisor / compatibility lane.
3. `scope_project` live broad write remains blocked pending mismatch adjudication.
4. `jobs answer` primary-path auth and chunk-contract normalization are already fixed.
5. public MCP `/health` already exists and remains part of the validation pack.

## 4. Independent runtime findings that shape V6

### 4.1 Knowledge substrate

Verified against the live EvoMap DB:

- planning atoms total: `36,567`
- planning active: `201`
- planning staged: `35,799`
- planning groundedness `= 0`: `36,363`
- planning groundedness `>= 0.6`: `204`
- planning quality `>= 0.6`: `32,285`
- planning quality `>= 0.7`: `16,985`

Interpretation:

- the problem is not content absence;
- the problem is scoring/promotion reachability.

### 4.2 Groundedness semantics

Two different groundedness thresholds exist today:

- generic gate default: `0.7`
- planning reviewed bootstrap path: `0.6`

Also, the generic groundedness checker gives `overall=1.0` when no path/unit/code-symbol anchors exist.
That means naive full-table promotion through the generic gate would be unsafe for pure-text planning atoms.

### 4.3 Planning grounding anchors

A sample of `1,000` planning staged atoms shows only about `19.5%` include runtime grounding anchors.

Interpretation:

- only a minority of staged planning atoms are safe candidates for direct `active` promotion;
- the larger population should flow through `candidate` and curated/runtime-pack style lanes unless and until stronger evidence exists.

### 4.4 KB hybrid runtime

The repo `.venv` runtime confirms:

- `fastembed` is installed and usable;
- `KBHub.search()` can produce vector-only hits;
- live `.openmind` state shows `kb_fts=941` and `kb_vectors=151`.

Interpretation:

- the current platform should treat KB hybrid as partially live and evidence-worthy;
- earlier “fastembed missing” claims were an interpreter/runtime mismatch, not a repo dependency absence.

## 5. V6 work packages

## A. Wrapper Surface Auto-Selection Hardening

### Objective

Make the wrapper behave like a product surface rather than a raw contract validator.

### Required implementation

1. Add an explicit surface-resolution step in [chatgptrest_call.py](/vol1/1000/projects/ChatgptREST/skills-src/chatgptrest-call/scripts/chatgptrest_call.py).
2. Preserve `coding-agent-v1` as the default when the request is narrow.
3. Auto-escalate to `advisor-agent` when the request explicitly requires broad public advisor capabilities, including at minimum:
   - `--role-id`
   - `--user-id`
   - `task_intake`
   - `workspace_request`
   - `contract_patch`
   - non-default broad `--depth`
   - planning/advisor-oriented goal families that depend on the broader advisor contract
4. Keep explicit `--agent-surface` as the highest-precedence override.
5. Ensure recovery hints and timeout/error messaging refer to the resolved lane rather than a stale hardcoded advisor-only contract.

### Acceptance

1. The current failing `tests/test_skill_chatgptrest_call.py` slice is green under `.venv`.
2. Requests that require advisor-only fields no longer fail preflight under the default wrapper behavior.
3. Narrow coding-agent calls still use `coding_agent_*` by default.

## B. Planning Bulk Scoring and Promotion Pipeline

### Objective

Create a safe, repeatable planning knowledge activation path that does not depend on one-off reviewed bootstrap actions.

### Required implementation

1. Add a new ops runner for planning bulk scoring/promotion, separate from the reviewed planning-maintenance script.
2. The new runner must:
   - operate on planning-scoped atoms only;
   - batch work in bounded chunks;
   - update groundedness for staged/candidate planning atoms;
   - distinguish between:
     - direct-active eligible atoms: planning atoms with runtime grounding anchors, acceptable quality, and passing groundedness;
     - candidate-only eligible atoms: acceptable planning atoms without runtime anchors, for later curated/runtime-pack use;
   - write structured artifacts and promotion evidence;
   - support dry-run and bounded live-run modes.
3. The runner must not directly equate `groundedness` to `quality_auto`.
4. The runner must not broad-write `active` for pure-text planning atoms with no runtime anchors.
5. The runner must include safe cadence controls:
   - batch size
   - max atoms per run
   - optional project filter
   - explicit dry-run/live mode separation

### Acceptance

1. A dry-run produces a machine-readable estimate of:
   - staged scanned
   - groundedness updated
   - candidate promotions
   - active promotions
2. A bounded live run produces fresh:
   - groundedness audit rows
   - promotion audit rows
   - monitor artifacts
3. Planning `active` count increases beyond the current `201` without violating the runtime-anchor rule.
4. Planning `candidate` count increases for pack-eligible atoms that are not safe for direct `active`.

## C. Promotion Scheduler Separation and Live Installation

### Objective

Stop conflating “reviewed pack maintenance” with “promotion scheduling”.

### Required implementation

1. Introduce a dedicated user systemd service/timer pair for the new planning bulk scoring/promotion runner.
2. Keep the existing reviewed planning-maintenance timer intact; do not overload it.
3. Install the new scheduler into live user systemd.
4. Enable it and capture evidence that it is scheduled independently.

### Acceptance

1. `systemctl --user list-unit-files` shows both:
   - reviewed planning-maintenance timer
   - planning bulk scoring/promotion timer
2. At least one live run artifact exists for the new scheduler.
3. The two timers have distinct responsibilities in docs and evidence.

## D. Planning Runtime Pack Refresh After Bulk Promotion

### Objective

Refresh the curated planning runtime slice after new planning candidate/active atoms exist.

### Required implementation

1. Re-run the reviewed planning pack export using the post-promotion state.
2. Capture whether the pack size changes and whether freshness advances.
3. If allowlist constraints block wider pack growth, record that explicitly instead of silently claiming success.

### Acceptance

1. A new runtime-pack bundle exists with a fresh timestamp.
2. The manifest is consistent and explicit about whether growth occurred.
3. The latest planning runtime pack is no longer frozen at the March 11 snapshot.

## E. KB Hybrid Runtime Hardening

### Objective

Freeze the service-runtime facts around hybrid KB retrieval so the upcoming user test is not relying on accidental interpreter differences.

### Required implementation

1. Add a narrow runtime verification step or artifact pack that proves:
   - the live service runtime uses `.venv`;
   - `fastembed` is importable in that runtime;
   - vector DB path exists;
   - a live/smoke hybrid query yields vector-enabled hits;
   - coverage counts are recorded (`kb_fts`, `vectors`).
2. Expose or record this state in a way suitable for operations evidence. This may be via `/health`, a dedicated ops script, or both.

### Acceptance

1. Evidence exists showing vector retrieval is truly usable in the same runtime used by the services.
2. The evidence is no longer based on system Python probes.

## F. Regression and Acceptance Recovery

### Objective

Restore a credible production validation baseline before the user performs manual testing.

### Required implementation

1. Fix the current wrapper/planning-plane regression slice under `.venv`.
2. Re-run:
   - `tests/test_skill_chatgptrest_call.py`
   - `tests/test_routes_agent_v3_planning_task_plane.py`
   - `tests/test_agent_v3_route_work_sample_validation.py`
3. Run any additional focused tests touched by the new bulk scoring/promotion runner and systemd integration.
4. If full-suite green is not achievable because of unrelated dirty worktree state, explicitly prove the remaining failures are outside the V6 touched surface.

### Acceptance

1. The targeted V6 regression slice is green.
2. Any remaining failures are documented and shown to be outside the V6 touched surface.

## G. Final Production-Readiness Evidence Pack

### Objective

Produce one final evidence pack for the user's upcoming manual test.

### Required implementation

1. Capture:
   - public MCP `/health`
   - coding-agent primary-path answer proof
   - KB hybrid runtime proof
   - planning bulk scoring/promotion run proof
   - planning runtime-pack refresh proof
   - regression suite proof
2. Write:
   - completion summary
   - residual risk note
   - walkthrough

### Acceptance

1. One evidence pack exists that can answer “is this production-grade enough to manually test right now?” without re-running the analysis.
2. Residual risk is limited to explicitly deferred strategic work, not hidden runtime blockers.

## 6. Execution order

V6 executes in this order:

1. freeze V6 plan + TODO anchor
2. wrapper surface auto-selection hardening
3. planning bulk scoring/promotion runner
4. dedicated promotion scheduler installation
5. post-promotion runtime-pack refresh
6. KB hybrid runtime verification hardening
7. regression slice recovery
8. final evidence pack and closeout

## 7. Explicit non-goals

V6 does not include:

1. global `scope_project` live broad backfill
2. broad cross-project KB/EvoMap system merge
3. retirement of `advisor_agent_*`
4. aggressive active promotion of pure-text planning atoms without runtime anchors

Those remain later strategic work, not production-readiness prerequisites for this wave.
