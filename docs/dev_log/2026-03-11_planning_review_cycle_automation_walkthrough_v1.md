# 2026-03-11 Planning Review Cycle Automation Walkthrough v1

I moved the planning line one step past “scripts exist” into “this can be run as a stable maintenance cycle”.

Before this round, the pieces were there, but the operator still had to manually remember the order:

1. refresh snapshot
2. find the right pack
3. tell reviewer lanes where to write JSON
4. merge reviewer outputs
5. overlay onto the full baseline
6. validate on a temp DB
7. maybe apply to canonical

That is fragile. It is also exactly the kind of flow that regresses after a week because nobody remembers which snapshot directory is the true decision baseline.

## What I tightened

I added [run_planning_review_cycle.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_review_cycle.py) as the maintenance entrypoint.

It does two useful things beyond simple orchestration:

- It emits a reviewer manifest with fixed output paths for `gemini_no_mcp`, `claudeminmax`, and `codex_auth_only`, so the external reviewer lanes can plug in without hand-wiring each cycle.
- It keeps refresh / merge / apply semantics together in one artifact package via `cycle_summary.json`.

## The real bug I found while exercising it

When I first ran the script on live state, refresh still surfaced the same `36` docs as pending review. That was wrong, because the reviewed `v3` baseline had already been applied to canonical.

The actual root cause was not in the new script. It was in [planning_review_refresh.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_refresh.py):

- `_decision_file()` still only recognized `v2/default`
- refresh also treated the immediately previous snapshot as the only possible decision source

That meant a `refresh-only` snapshot with no decision TSV could hide the latest prior refresh snapshot that actually contained `v3`.

I fixed both:

- `v3+` decision files are now recognized
- refresh now reuses the latest prior decision snapshot, even if the immediate previous snapshot was just a no-op refresh

## Why this matters

Without this, planning maintenance looks superficially automated but behaves like a loop reset:

- you think you have a stable reviewed baseline
- you run refresh again
- it silently compares against the wrong decision source
- you re-review old docs for no reason

That is not just annoying. It destroys trust in the reviewed slice.

## End state after the fix

Running:

```bash
./.venv/bin/python ops/run_planning_review_cycle.py
```

now yields:

- [20260311T042646Z](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_review_plane_refresh/20260311T042646Z)
- `review_needed_docs = 0`
- `pack_items = 0`
- `decision_source_dir = artifacts/monitor/planning_review_plane_refresh/20260311T032642Z`

That is the right outcome. It means the maintenance loop sees the already-reviewed planning baseline as current, instead of trying to rebuild it from an older source.

## What this enables next

The planning line is still intentionally bounded:

- reviewed baseline maintenance
- bootstrap active slice maintenance
- no runtime cutover

But now the maintenance side is finally repeatable enough that future reviewer-lane work can be driven by a single cycle manifest instead of manual directory surgery.
