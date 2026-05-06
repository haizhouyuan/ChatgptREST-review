# 2026-03-11 Planning Review Priority Bundle Walkthrough v1

The backlog audit told us something important:

- the planning backlog is huge
- but most of it is still archive/review-plane material

That means the next step cannot be “review more backlog”.
It has to be:

`review a smaller, better queue`

That is why I added [build_planning_review_priority_bundle.py](/vol1/1000/projects/ChatgptREST/ops/build_planning_review_priority_bundle.py).

## Why a priority bundle was needed

Before this round we had:

- a reviewed slice audit
- a backlog audit

But we still did not have a deterministic handoff artifact for the next review round.

Without that, the operator still has to improvise:

- which backlog docs matter
- which ones are just latest-output residue
- which ones are obviously noise

That is exactly where reviewer time gets wasted.

## What I made deterministic

The priority bundle now picks from unreviewed planning docs using a narrow queue contract:

- must still be outside the reviewed slice
- must not be `archive_only` or `controlled`
- high-signal buckets get positive priority
- obvious noise patterns are hard-excluded

The important part is the hard-exclusion.  
I initially only down-ranked `README/request/runlog/问 Pro`, and the tests showed those files could still sneak back in via positive bucket weighting. I changed that to an explicit exclusion gate.

## What the live bundle showed

The live `limit=50` queue came out as:

- `planning_outputs = 18`
- `planning_aios = 14`
- `planning_latest_output = 8`
- `planning_strategy = 8`
- `planning_budget = 2`

This is a much healthier shape than the raw backlog:

- it is no longer dominated by `planning_misc`
- it is no longer dominated by `_review_pack`
- it surfaces concrete execution / governance / strategy artifacts first

That is exactly what a reviewer lane should see.

## What this means for the next step

At this point the planning maintenance line now has 4 layers:

1. reviewed slice audit
2. backlog audit
3. cycle automation
4. deterministic priority bundle

So if the next round expands, it should expand by feeding this queue into reviewer lanes, not by reopening the entire planning backlog.
