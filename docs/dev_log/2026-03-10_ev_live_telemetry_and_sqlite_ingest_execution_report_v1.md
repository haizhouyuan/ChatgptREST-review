# 2026-03-10 EV Live Telemetry And SQLite Ingest Execution Report v1

## Scope

This execution report covers two overnight objectives:

1. Wire live agent telemetry into canonical EvoMap so agent work can flow from producer to archive/event bus and into EvoMap knowledge.
2. Ingest all discovered database files into canonical EvoMap as archive-plane inventory records.

Canonical target DB:

- `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db`

Relevant code commits:

- `0e138a6` — live telemetry identity contract + runtime wiring
- `7918f3e` — accept archive telemetry envelopes in live EvoMap ingest
- `f77b638` — SQLite inventory ingest into canonical EvoMap
- `ff715de` — classify non-SQLite database files in inventory ingest
- maint repo `fee096e` — mirror agent activity into ChatgptREST telemetry

## Result

### 1. Live telemetry chain

Status: passed

End-to-end smoke was run against a temporary Advisor API instance on `127.0.0.1:18719` with temporary DB paths.

Producer:

- `/vol1/maint/ops/scripts/agent_activity_event.py`

Path validated:

- maint producer emits archive envelope JSONL
- same producer best-effort mirrors to `/v2/telemetry/ingest`
- `TelemetryIngestService` emits `TraceEvent`
- `ActivityIngestService.register_bus_handlers()` consumes the event
- canonical EvoMap knowledge DB receives `documents / episodes / atoms / evidence`

Smoke result after final fix:

- temporary EvoMap DB counts: `documents=1`, `episodes=2`, `atoms=2`, `evidence=2`, `entities=4`, `edges=4`
- created atom `task result: smoke-live-closeout-3 by codex`
- created atom `commit HEAD in ChatgptREST`

The key bug found by live smoke was real:

- `register_bus_handlers()` was still flattening only the old payload shape
- `/v2/telemetry/ingest` now sends full archive envelope payloads
- effect: events reached `trace_events`, but no EvoMap atoms were created
- fix landed in `7918f3e`

### 2. Database inventory ingest

Status: passed

Command executed:

```bash
./.venv/bin/python ops/ingest_sqlite_inventory_to_evomap.py \
  --output-dir artifacts/monitor/evomap/sqlite_ingest/20260310_full_v2
```

Artifacts:

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap/sqlite_ingest/20260310_full_v2/summary.json)
- [summary.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap/sqlite_ingest/20260310_full_v2/summary.md)

Discovery result:

- discovered DB files: `70`
- project split:
  - `chatgptrest`: `30`
  - `maint`: `28`
  - `openmind_home`: `12`

Ingest result:

- inventory documents inserted/updated: `70`
- inventory episodes inserted/updated: `299`
- inventory atoms inserted/updated: `299`
- inventory evidence inserted/updated: `299`

Canonical DB delta:

- documents: `7136 -> 7206` (`+70`)
- episodes: `43625 -> 43924` (`+299`)
- atoms: `95239 -> 95538` (`+299`)
- evidence: `79816 -> 80115` (`+299`)
- edges unchanged: `82789`

Failure classification after final rerun:

- `20` files: `not a sqlite database file`
- `6` files: `zero-byte sqlite file`
- `2` files: `sqlite_master scan failed: database is locked`

Interpretation:

- the non-SQLite group is mostly `.db`-suffixed Neo4j store files under maint state
- the zero-byte group is expected placeholder/legacy files
- the two locked files are browser profile DBs still held by Chrome

## What Was Ingested

The ingest is intentionally archive-plane inventory, not row-level authoritative merge.

For each discovered DB file:

- one `Document` records the file path, project, role, size, and inventory metadata
- one database-level `Episode`
- one database summary `Atom`
- one table/view-level `Episode` per object
- one schema/content-profile `Atom` per table/view
- one `Evidence` record per generated atom

Examples now present in canonical EvoMap:

- legacy `~/.openmind/kb_search.db`
- legacy `~/.openmind/evomap_knowledge.db`
- canonical `data/evomap_knowledge.db`
- `state/jobdb.sqlite3`
- `state/knowledge_v2/canonical.sqlite3`
- maint export slices under `/vol1/maint/exports/...`

## Constraints

- This work does **not** merge foreign DB rows into canonical truth tables.
- It builds retrievable inventory knowledge about those databases.
- Non-SQLite `.db` files are recorded as archive inventory with explicit error classification.
- Browser-locked databases remain partially inventoried until their handles are released.

## Conclusion

Both requested objectives were achieved:

- EV live telemetry now works across producer, API, EventBus, and canonical EvoMap ingest.
- All discovered database files were ingested into canonical EvoMap as structured database inventory records, with failure reasons classified rather than silently skipped.
