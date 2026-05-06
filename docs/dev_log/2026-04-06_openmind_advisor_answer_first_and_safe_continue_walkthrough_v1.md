# 2026-04-06 OpenMind Advisor Answer-First And Safe-Continue Walkthrough v1

## What I Changed

I stopped treating the OpenClaw plugin as a debug console and pushed it closer
to a user-facing result layer.

Before this batch:

1. `openmind_advisor_ask` printed system metadata before the answer
2. fail-close surfaced machine labels such as `same_session_repair`
3. simple follow-up asks still depended too strictly on explicit upstream
   `taskId` forwarding

After this batch:

1. users see the answer first
2. fail-close is rendered as "not yet deliverable / what is missing / what to
   do next"
3. obvious continuation asks can auto-bind to the only visible runtime task
   without widening the backend contract

## Why This Matters

This change does not make the planning backend smarter.

It makes the actual OpenClaw experience more usable:

- the result is cleaner to read
- a follow-up ask is less brittle
- users no longer need to mentally strip away `Route/Session/Run/Job` noise

## Why I Kept It Narrow

I did not move this logic into the planning backend.

That would be the wrong layer.

The planning backend is still a machine contract.
The OpenClaw plugin is the right place to:

1. translate backend result state into user-facing text
2. add a conservative continuation fallback based on runtime task visibility

## Evidence

This batch is validated by plugin-surface and live-gate regression tests:

- `tests/test_openclaw_cognitive_plugins.py`
- `tests/test_openmind_advisor_truth_surface.py`
- `tests/test_openclawbot_planning_task_plane_live_completion_gate.py`

The key point is not "more backend capability".
The key point is "the OpenClaw ingress/egress around the planning mainline is
less brittle and less machine-facing".
