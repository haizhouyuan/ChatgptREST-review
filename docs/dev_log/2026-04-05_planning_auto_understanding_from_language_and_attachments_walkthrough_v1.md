# 2026-04-05 Planning Auto-Understanding From Language And Attachments Walkthrough v1

## What I Changed

I tightened one of the last "feels too internal" parts of the planning
experience.

Before this batch, the system was already better at:

- choosing a stable main path
- keeping same-task continuity
- failing closed on weak full-planning output

But there was still a user-facing gap:

- some asks were only provably correct because the test injected explicit
  `planning_task_type`

I changed that by making the system listen to two things users already provide:

1. the natural language in the request itself
2. the attachment metadata already attached to the request

## What Is Better Now

The practical effect is:

1. `请整理一版业务推进方案和下一步计划` can now directly enter
   `planning_general`
2. `请先帮我整理一下今天材料` can now directly enter `meeting_summary` when
   the attachment inventory already says the material is a meeting transcript
3. the user-readiness bundle no longer depends on explicit `task_type` for the
   common frozen planning profiles

So the product now feels more like:

- describe the work normally
- attach the real materials
- let the system infer the right planning path

instead of:

- describe the work
- also remember the system's internal planning labels

## Why I Kept It Narrow

I still did not rewrite the whole front-door scenario matcher.

GitNexus continues to flag `resolve_scenario_pack` and `_matched_planning_profile`
as `CRITICAL`, so I kept the change bounded:

- add a small set of `planning_general` language signals
- add transcript-aware attachment signals for `meeting_summary`
- prove the behavior through route tests and the user-readiness pack

## Evidence

The frozen evidence bundle for this slice is:

- `docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/`

The most important new signals in that pack are:

- `attachment_signals_auto_understood = true`
- `planning_general_profile.profile_selected = true` without explicit task type
- `meeting_summary_attachment_profile.profile_selected = true`

## Why It Matters

This matters because it removes another layer of "operator knowledge" from the
product.

Users should not need to know the internal planning taxonomy just to get a
normal planning result. This batch moves the system closer to the intended
experience:

- say what work you need
- provide the materials you already have
- let the system pick the planning shape and lane on its own
