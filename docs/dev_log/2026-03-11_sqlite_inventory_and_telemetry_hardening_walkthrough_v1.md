# 2026-03-11 SQLite Inventory And Telemetry Hardening Walkthrough v1

## Why this work was necessary

The previous EV inventory/telemetry landing fixed real contract gaps, but three defects remained:

- sqlite inventory leaked sampled operational row content into canonical EvoMap
- sqlite inventory described the canonical target DB inside itself by default
- telemetry replay lost upstream event identity on the EventBus path

Those were not paper issues. The first one had already written risky content into canonical EvoMap and archived JSON summaries.

## What I changed

### SQLite inventory

I treated the inventory output as archive-plane metadata only.

- Text sample values now default to descriptor form: `type`, `length`, `sha256`, `redacted=true`
- enum-like machine fields remain readable when useful (`status`, `state`, `type`, `source`, etc.)
- the CLI now excludes `--target-db` by default and requires `--include-target-db` for intentional self-inventory

### Telemetry identity

I did not redesign the EventBus.

Instead I made the existing path stable:

- preserve `upstream_event_id`
- use it as `TraceEvent.event_id` when telemetry callers provide one
- keep both bus-level and upstream ids available inside ingest metadata
- hash generic activity atoms/episodes from upstream identity instead of volatile bus-only ids

That keeps the patch narrow even though `register_bus_handlers()` is high-risk/critical in GitNexus impact analysis.

## Live cleanup

Because the first defect had already materialized, code fixes alone were not enough.

I removed the existing `sqlite_inventory` slice from canonical EvoMap, deleted the two unsafe artifact directories, and re-ran inventory with the hardened code into:

- `artifacts/monitor/evomap/sqlite_ingest/20260311_safe_v1/`

The remediated run produced `69` safe inventory documents and excluded the canonical target DB.

## What I verified

- no raw `conversation_url` values remain in canonical sqlite inventory evidence
- no raw `{\"prompt\":\"secret\"}` sample remains in canonical sqlite inventory evidence
- no `sqlite_inventory` document points at `/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db`
- EventBus replay with the same upstream id dedupes down to one canonical atom
- TelemetryIngestService replay with the same upstream id dedupes down to one EventBus event and one canonical atom

## Commits

- `731065a` `fix: harden sqlite inventory ingest defaults`
- `237c108` `fix: preserve upstream telemetry event identity`

This walkthrough intentionally excludes unrelated dirty-worktree files that were already present before the task.
