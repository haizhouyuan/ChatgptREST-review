# Promotion Low-Active Root-Cause Diagnosis V1

Date: 2026-04-08

Primary evidence bundle:

- [preflight summary json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T224249Z/preflight_summary.json)
- [preflight summary md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/next_stage_preflight/20260407T224249Z/preflight_summary.md)
- [promotion inventory runner](/vol1/1000/projects/ChatgptREST/ops/report_evomap_promotion_inventory.py)
- [planning-review maintenance runner](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_maintenance.py)

## 1. Diagnosis

The dominant cause of the low active ratio is **scheduling absence**, not proven rejection by the groundedness gate.

This diagnosis is evidence-backed.

## 2. Evidence

### 2.1 Inventory state is still severely skewed toward staged atoms

Latest live counts:

- atoms: `104123`
- active: `202`
- candidate: `25`
- staged: `103354`
- archived: `542`
- active ratio: `0.00194`

This confirms the earlier concern remains real.

### 2.2 The audit window is stale

From the latest preflight:

- first audit event: `2026-03-11T02:36:28Z`
- last audit event: `2026-03-11T04:01:30Z`
- last audit age: `27.779 days`

This is not a healthy continuously-running promotion loop.

### 2.3 The runtime scheduler is absent in the live environment

The scheduling observation in the evidence pack shows:

- timer unit not found
- timer inactive
- `systemctl --user list-timers` returns `0 timers listed`

That is enough to explain why the reviewed promotion path is not advancing.

### 2.4 The audit history does not yet prove gate rejection as the main bottleneck

Promotion audit transitions are present:

- `candidate -> active`: `273`
- `active -> candidate`: `168`
- `staged -> candidate`: `61`

Groundedness score bands show many high-scoring reviewed cases:

- `>=0.9`: `273`
- `malformed`: `229`
- `missing`: `3`

This does not support the claim that "groundedness is simply too strict" as the dominant first-order blocker.

### 2.5 The dominant failure mode is already explicit in the evidence pack

The preflight output itself states:

- `dominant_failure_mode = scheduling_absence`
- rationale: promotion/maintenance timer is not installed or not scheduled, and `promotion_audit` has not advanced recently

## 3. Decision

Current decision:

- root cause = `scheduling_absence`
- throughput tuning = **not yet justified**
- broad threshold changes = **not yet justified**
- first corrective action = restore and verify a live maintenance schedule

## 4. What is justified now

Justified now:

1. Treat reviewed promotion scheduling as a release-shape requirement.
2. Keep maintenance runs observable and rerunnable.
3. Re-check inventory after maintenance is actually scheduled and observed advancing.

Not yet justified:

1. Broad groundedness threshold changes.
2. Large-scale promotion cleanup or mass status rewrites.
3. Claims that the promotion model is fundamentally wrong before the scheduler is restored.

## 5. Operational implication

The promotion subsystem is no longer opaque:

- inventory exists
- maintenance runners exist
- evidence pack exists

But the runtime is still not behaving like a continuously operating promotion loop.

The right next step is not "tune the scoring model harder".

The right next step is:

- restore scheduling
- verify audit movement
- then reassess whether gate thresholds are truly the bottleneck
