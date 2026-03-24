# 2026-03-11 SQLite Inventory And Telemetry Hardening v1

## Scope

Address three verified findings from the 2026-03-11 review:

1. SQLite inventory embedded live sampled row values from operational databases into canonical EvoMap atoms/evidence.
2. The default inventory command discovered and ingested the canonical target DB into itself.
3. Live telemetry lost upstream `event_id` on the EventBus path, so replay/dedup was unstable.

## Code Changes

### 1. SQLite inventory hardening

Files:

- `chatgptrest/evomap/knowledge/sqlite_inventory.py`
- `ops/ingest_sqlite_inventory_to_evomap.py`
- `tests/test_sqlite_inventory.py`

Behavior changes:

- Added redaction/allowlist policy for sampled SQLite row values.
- Operational roles (`job_store`, `memory_store`, `event_bus_store`, `effects_store`, `controller_lanes`, browser profile stores, EvoMap stores, issue canonical stores, etc.) now redact sampled text values into type/length/hash descriptors.
- Safe enum-like columns such as `status`, `state`, `type`, `source`, `provider`, `model` remain readable.
- Added `filter_sqlite_databases()` and changed the CLI to exclude `--target-db` from discovery by default.
- Added `--include-target-db` for explicit self-inventory runs.

### 2. Telemetry upstream identity preservation

Files:

- `chatgptrest/telemetry_contract.py`
- `chatgptrest/cognitive/telemetry_service.py`
- `chatgptrest/evomap/activity_ingest.py`
- `tests/test_activity_ingest.py`
- `tests/test_telemetry_contract.py`
- `tests/test_advisor_runtime.py`

Behavior changes:

- Telemetry payloads now preserve `upstream_event_id` as a first-class identity field.
- `TelemetryIngestService.ingest()` now emits `TraceEvent.event_id=upstream_event_id` when the caller supplies one, instead of always creating a fresh bus-only id.
- Duplicate EventBus emits now short-circuit correctly inside telemetry ingest.
- `ActivityIngestService.register_bus_handlers()` preserves both the EventBus event id and upstream event id.
- Generic activity ingest now fingerprints episodes/atoms using `upstream_event_id` when present, stabilizing replay dedupe.

## Live Remediation

The unsafe inventory content already written into canonical EvoMap was removed and regenerated safely.

Canonical DB remediation:

- deleted legacy `sqlite_inventory` docs: `70`
- deleted legacy `sqlite_inventory` episodes: `299`
- deleted legacy `sqlite_inventory` atoms/evidence tied to those docs
- re-ran safe inventory ingest into canonical DB

Post-remediation inventory state:

- `documents(source='sqlite_inventory') = 69`
- `target self docs = 0`
- `evidence LIKE '%conversation_url%https://%' = 0`
- `evidence LIKE '%\"prompt\":\"secret\"%' = 0`

Safe artifact output:

- `artifacts/monitor/evomap/sqlite_ingest/20260311_safe_v1/summary.json`
- `artifacts/monitor/evomap/sqlite_ingest/20260311_safe_v1/summary.md`

The prior unsafe artifact directories `20260310_full` and `20260310_full_v2` were removed.

## Validation

Tests:

```bash
./.venv/bin/pytest -q tests/test_sqlite_inventory.py
./.venv/bin/pytest -q tests/test_sqlite_inventory.py tests/test_activity_ingest.py tests/test_telemetry_contract.py tests/test_advisor_runtime.py
./.venv/bin/pytest -q tests/test_cognitive_api.py -k telemetry_ingest
./.venv/bin/python -m py_compile \
  chatgptrest/evomap/knowledge/sqlite_inventory.py \
  ops/ingest_sqlite_inventory_to_evomap.py \
  chatgptrest/telemetry_contract.py \
  chatgptrest/cognitive/telemetry_service.py \
  chatgptrest/evomap/activity_ingest.py \
  tests/test_sqlite_inventory.py \
  tests/test_activity_ingest.py \
  tests/test_telemetry_contract.py \
  tests/test_advisor_runtime.py
```

Manual reproductions after fix:

- sampled `jobdb.sqlite3` rows now show redacted descriptors for `input_json`, `params_json`, `conversation_url`
- discovery excludes `evomap_knowledge.db` unless `--include-target-db` is passed
- emitting two EventBus `team.run.created` events with different bus ids but the same upstream `event_id=external-123` now stores only one canonical EvoMap atom
- ingesting the same telemetry event twice through `TelemetryIngestService` now produces one EventBus row and one canonical EvoMap atom

## Result

The three reviewed findings are now closed at both the code-path level and the live canonical DB level.
