# 2026-03-10 Telemetry Contract P0 Alignment v1

## Goal

Start the implementation phase after closing GitHub issue `#114`.

This P0 slice fixes the first concrete blocker identified during review:

- `agent_activity_event.py` emits nested archive envelopes
- `chatgptrest/evomap/activity_ingest.py` previously expected a different flat payload shape
- `ActivityIngestService.register_bus_handlers()` also assumed a typed `subscribe(event_type, handler)` API that does not match the current `EventBus.subscribe(handler)` contract

## Scope

Files changed in this slice:

- `chatgptrest/evomap/activity_ingest.py`
- `tests/test_activity_ingest.py`

## Implemented

### 1. Archive-envelope compatibility

`ActivityIngestService` now normalizes both:

- legacy flat live-ingest payloads
- `openmind-v3-agent-ops-v1` archive envelopes emitted by `agent_activity_event.py`

Covered event families in this slice:

- `agent.git.commit`
- `agent.task.closeout`

### 2. Identity preservation

Normalized commit/closeout ingestion now preserves key identity fields into EvoMap metadata:

- event type
- schema version
- source
- task ref
- trace id
- session id
- event id
- repo name/path/branch/head
- status / pending reason / pending scope for closeout

The fields are stored in:

- `Episode.source_ext`
- `Atom.applicability`

This keeps raw telemetry authoritative while giving EvoMap enough identity context to support future mapping into review/service planes.

### 3. Stable dedupe across payload shapes

Commit and closeout atoms now use stable semantic fingerprints instead of hashing the raw input JSON.

Result:

- the same commit is no longer duplicated just because it arrived in a different payload shape
- closeout atoms use a stable event fingerprint instead of raw JSON layout

### 4. EventBus registration fixed

`register_bus_handlers()` now supports both contracts:

- typed pub-sub: `subscribe(event_type, handler)`
- current ChatgptREST `EventBus`: `subscribe(handler)`

For the generic `EventBus`, the ingest service now wraps handlers with an event-type filter so live registration actually works.

## Validation

Executed:

```bash
./.venv/bin/pytest -q tests/test_activity_ingest.py tests/test_activity_extractor.py
./.venv/bin/python -m py_compile chatgptrest/evomap/activity_ingest.py tests/test_activity_ingest.py
```

New regression coverage includes:

- archive commit envelope ingestion
- archive closeout envelope ingestion
- generic `EventBus.subscribe(handler)` compatibility

## Remaining gaps

This slice intentionally does **not** finish full telemetry unification.

Still pending:

- maint-side producers do not yet emit richer live identity fields consistently into archive JSONL
- `TraceEvent` ↔ archive envelope catalog/mapping is still implicit, not formalized
- experience extraction and review-plane integration are not started here

## Decision

The execution path remains:

1. align producer/consumer schema and identity handling
2. widen producer coverage
3. add experience extraction
4. connect review/service governance

This commit only covers step 1, first cut.
