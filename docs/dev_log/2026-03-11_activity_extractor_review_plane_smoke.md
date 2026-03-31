# 2026-03-11 Activity Extractor Review-Plane Smoke

## Goal

Prove the posthoc `agent_activity JSONL -> ActivityExtractor -> staged candidate atoms`
path is still healthy after the execution-extension preservation work.

This is intentionally **not** a runtime retrieval test. It validates the
review/candidate plane.

## What the smoke does

The smoke script:

- writes one synthetic `agent.task.closeout` event
- writes one synthetic `agent.git.commit` event
- runs `ActivityExtractor` against a temp JSONL directory and temp EvoMap DB
- verifies:
  - 2 atoms created
  - both remain `promotion_status=staged`
  - both remain `status=candidate`
  - execution extensions survive into atom `applicability`
  - identity fields survive into episode `source_ext`

## Why this matters

The mainline execution telemetry work now has two validated paths:

1. live canonical materialization via `/v2/telemetry/ingest`
2. posthoc review-plane extraction via `ActivityExtractor`

That keeps the contract aligned with the `#114` boundary:

- live/runtime plane continues to use `TraceEvent`
- review/candidate plane can still absorb opaque/posthoc envelopes without
  promoting them into active runtime knowledge

## Files

- [run_activity_extractor_review_plane_smoke.py](/vol1/1000/projects/ChatgptREST/ops/run_activity_extractor_review_plane_smoke.py)
- [test_activity_extractor_review_plane_smoke.py](/vol1/1000/projects/ChatgptREST/tests/test_activity_extractor_review_plane_smoke.py)
