# 2026-03-10 Telemetry Contract P0 Alignment Walkthrough v1

## What I changed

I closed GitHub issue `#114` and immediately executed the first implementation slice instead of leaving the architecture note open-ended.

The code change focused on the drift that was already real in production shape:

- archive JSONL events from `/vol1/maint/ops/scripts/agent_activity_event.py`
- live EvoMap ingestion in `chatgptrest/evomap/activity_ingest.py`

## Why this cut first

This was the lowest-risk, highest-leverage place to start:

- direct blast radius was `MEDIUM` and limited to `activity_ingest.py` plus its tests
- it fixed a real mismatch instead of writing another planning document
- it preserves future room for the stronger `TraceEvent` vs archive-envelope split

## Key outcomes

- `ingest_commit_event()` and `ingest_closeout_event()` now accept current archive envelopes
- event identity is preserved in EvoMap metadata instead of being discarded
- `register_bus_handlers()` now works with the real `EventBus.subscribe(handler)` API
- tests now cover archive envelopes and generic EventBus registration

## What I deliberately did not do

- I did not redefine `TraceEvent`
- I did not move raw telemetry directly into service retrieval logic
- I did not start the experience-extractor layer yet
- I did not touch maint-side emitters in this slice

## Verification

Passed:

```bash
./.venv/bin/pytest -q tests/test_activity_ingest.py tests/test_activity_extractor.py
./.venv/bin/python -m py_compile chatgptrest/evomap/activity_ingest.py tests/test_activity_ingest.py
```

## Next useful step

The next implementation cut should formalize the shared identity contract and event catalog:

- `trace_id`
- `session_id`
- `job_id`
- `issue_id`
- `task_ref`
- `repo`
- `branch`
- `commit_sha`
- `agent`
- `provider`
- `model`
- `source`

That can then be pushed outward to maint-side emitters and inward to review-plane extraction.
