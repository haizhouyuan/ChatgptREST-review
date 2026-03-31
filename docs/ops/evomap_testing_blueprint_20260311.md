## EvoMap Testing Blueprint

This blueprint defines how to validate EvoMap as a real runtime capability, not just a
signal sink or governance store.

### Acceptance chain

EvoMap must be validated across the full chain:

1. canonical ingest
2. governed state
3. runtime consumer
4. business loop

### Test layers

#### 1. Path and DB contract

Goal: runtime read/write paths must only use the canonical knowledge DB.

Primary coverage:
- `tests/test_openmind_store_paths.py`
- `tests/test_routes_evomap.py`
- `tests/test_advisor_consult.py`

Pass criteria:
- runtime helpers resolve to `data/evomap_knowledge.db`
- legacy `~/.openmind/evomap_knowledge.db` is archive-only unless explicitly requested
- zero-byte or legacy-home fallbacks do not silently hijack runtime reads

#### 2. Ingest contract

Goal: producer/consumer schemas stay aligned and ingested data is safe for canonical storage.

Primary coverage:
- `tests/test_activity_ingest.py`
- `tests/test_telemetry_contract.py`
- `tests/test_sqlite_inventory.py`

Pass criteria:
- live bus and archive envelope preserve upstream identity
- replay of the same upstream event is idempotent
- sqlite inventory redacts sensitive operational rows
- inventory discovery excludes the target canonical DB by default

#### 3. Runtime visibility gate

Goal: runtime retrieval only exposes states that are intended to be queryable.

Primary coverage:
- `tests/test_evomap_runtime_contract.py`
- `tests/test_advisor_consult.py`

Pass criteria:
- `promotion_status=active|staged` may be returned
- `promotion_status=candidate` is not returned to runtime consumers
- superseded atoms are excluded even if they still match FTS
- consult helper also enforces its groundedness gate for returned EvoMap hits
- consult/recall helpers inherit the same gate as low-level retrieval

#### 4. Governance and promotion

Goal: promotion changes runtime visibility only when governance says it should.

Primary coverage:
- `tests/test_promotion_engine.py`
- `tests/test_evomap_chain.py`
- `tests/test_evomap_review_experiment.py`
- `tests/test_evomap_evolution.py`

Pass criteria:
- staged/candidate/active transitions are valid and auditable
- review-only or candidate material does not leak into runtime retrieval
- supersession chains stay consistent

#### 5. Business vertical slices

Goal: at least one real runtime consumer benefits from EvoMap.

Primary slices:
- issue domain query/export
- telemetry/activity ingest
- advisor consult/recall

Pass criteria:
- one canonical consumer reads EvoMap in its normal request path
- sources attribution includes EvoMap when relevant
- feedback/evidence can flow back into governance without polluting runtime answers

#### 6. Ops and regression

Goal: data growth or new imports do not silently degrade the runtime.

Suggested checks:
- canonical DB size and atom counts
- promotion-state distribution
- evidence coverage
- recall latency
- source distribution by domain

### Default execution order

```bash
./.venv/bin/pytest -q \
  tests/test_openmind_store_paths.py \
  tests/test_activity_ingest.py \
  tests/test_telemetry_contract.py \
  tests/test_sqlite_inventory.py \
  tests/test_evomap_runtime_contract.py \
  tests/test_advisor_consult.py \
  tests/test_routes_evomap.py

./.venv/bin/pytest -q \
  tests/test_promotion_engine.py \
  tests/test_evomap_chain.py \
  tests/test_evomap_review_experiment.py \
  tests/test_evomap_evolution.py

./.venv/bin/pytest -q \
  tests/test_cognitive_api.py \
  tests/test_advisor_runtime.py \
  tests/test_phase4_evomap.py \
  tests/test_evomap_e2e.py
```

### Minimum live smoke

After targeted pytest passes, run three live checks:

1. telemetry ingest creates canonical EvoMap material
2. issue-domain query/export can read canonical results
3. advisor recall/consult can surface EvoMap-backed context when relevant

### Current priority gaps

As of 2026-03-11, the high-value gaps to keep locked are:

- runtime visibility gate
- canonical source attribution in consult/recall
- business-loop validation for real consumers

The ingest-side replay, redaction, and target-db exclusion cases are already covered in
the current test suite and should remain part of the default regression run.
