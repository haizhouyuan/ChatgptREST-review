# 2026-04-09 OpenMind Production-Grade Execution Walkthrough v1

## What was done

This wave completed the remaining production-grade plan phases after the earlier canary-readiness launch.

The practical goals were:

1. make the remaining plan phases real instead of declarative
2. keep the final status honest
3. avoid fake-green promotion or recall claims

## Main corrective work

### 1. Retrieval guard for `planning_controlled`

`planning_controlled` targeted documents are allowed to become `active`, but they must not leak into non-planning surfaces.

So retrieval now hides `planning_controlled` atoms from surfaces other than `PLANNING_EXPLICIT_PATH`, even when they are `active`.

Files:

- `chatgptrest/evomap/knowledge/retrieval.py`
- `tests/test_evomap_runtime_contract.py`

### 2. Narrow active promotion for controlled targeted planning material

A new runner was added:

- `ops/run_planning_controlled_active_promotion.py`

This runner only promotes a very narrow slice:

- planning source only
- `source_bucket = planning_controlled`
- only targeted re-ingest documents with explicit `query_hits`
- only `candidate`
- only `qa` / `decision`
- noisy question-shape denylist
- quality threshold
- document-groundedness threshold
- per-query cap

This avoided broadening the existing promotion engine just to fix one rollout-critical bucket.

### 3. Recall benchmark posture hardening

The benchmark posture logic was made stricter for:

- dossier-style asks that only have bridge recall
- generic visit-prep asks with bridge-only recall

This is benchmark honesty, not live routing behavior.

Files:

- `ops/run_evomap_recall_production_benchmark.py`
- `tests/test_run_evomap_recall_production_benchmark.py`

### 4. Live evidence reruns

After code/test stabilization, the following were rerun on the current live DB:

- planning controlled active promotion
- EvoMap promotion inventory
- EvoMap recall production benchmark
- OpenMind production health
- OpenMind production regression
- OpenMind canary scorecard
- OpenMind watch-window ledger
- OpenMind graduation gate

## Why this mattered

Before this wave:

- `planning_controlled` had zero active atoms
- promotion warn was still critical-rollout-relevant
- recall boundary posture was not fully honest

After this wave:

- `planning_controlled active = 31`
- `critical_rollout.buckets_without_active_atoms = []`
- `critical_rollout.bounded_to_noncritical_only = true`
- recall moved to `pass`

## Final outcome

The stack is now in the strongest truthful state available on 2026-04-09:

- `packet = pass`
- `recall = pass`
- `promotion = warn` but bounded to non-critical backlog only
- `crystal = pass`
- canary scorecard still says `launch_canary_watch`
- graduation gate still says `hold`

The remaining `hold` is because the watch window is still running, not because the critical rollout slice is incomplete.
