# 2026-03-11 EvoMap Activation Pack

## Goal

Turn the one-off manual EvoMap recall activation into a repeatable narrow
operation that:

- selects a small set of staged atoms
- evaluates groundedness using the existing P2 checker
- writes groundedness + groundedness_audit
- does **not** widen retrieval gates
- does **not** change promotion status

## What landed

- Added [`ops/run_evomap_activation_pack.py`](../../ops/run_evomap_activation_pack.py)
- Added [`tests/test_evomap_activation_pack.py`](../../tests/test_evomap_activation_pack.py)

The tool supports:

- `--source ...` or explicit `--atom-id ...` selection
- staged-only packs by default
- dry-run by default
- `--apply` to persist groundedness and audit rows
- optional `--report-json`

## Runtime findings

### 1. Dry-run was immediately useful

Running a broad dry-run on `chatgptrest/maint/agent_activity` sources showed that
most staged atoms still fail the consult-visible threshold. That confirmed the
right next step is a **narrow pack**, not a broad promotion wave.

### 2. Live canonical DB currently has write contention

Applying the pack while `chatgptrest-api.service` was live hit:

- `sqlite3.OperationalError: database is locked`

This was not just a script problem. The live API was also logging the same lock
while processing `agent.git.commit` activity ingest against
`data/evomap_knowledge.db`.

Because `KnowledgeDB._insert()` has a CRITICAL blast radius, I did **not** fold a
DB-wide concurrency change into this same round. Instead:

- the activation-pack tool got `busy_timeout + retry`
- the first live apply was executed inside a short maintenance window

## First live activation pack

Applied atom ids:

- `at_act_46e169011ca85fb0`
- `at_act_522c334d29bf0cf7`
- `at_act_1b0298b1884b2901`
- `at_act_bc040cc193db78e4`
- `at_act_f4df4992cfc7b701`

All five are `agent_activity` commit atoms for `ChatgptREST`, all with:

- `promotion_status = staged`
- `overall_score = 1.0`

After apply:

- all 5 atoms had `groundedness = 1.0`
- 5 new `groundedness_audit` rows existed
- runtime recall returned `sources.evomap = 1` for:
  - `commit 0e567e6a on ChatgptREST`
  - `commit bda287e3 on ChatgptREST`

## Why this matters

This is the first repeatable pack-level proof that EvoMap can move from:

- telemetry/archive ingestion

to:

- staged runtime knowledge with consult-visible groundedness

without changing the runtime retrieval gate.

## Next

1. Keep activation packs narrow and source-scoped.
2. Build the next pack from clearly useful `agent_activity` / `issue_domain`
   atoms, not from broad `planning/antigravity` staging floods.
3. Treat live DB lock contention as its own infra item:
   - likely `KnowledgeDB` write-path busy-timeout / retry hardening
   - not part of this activation-pack change set
