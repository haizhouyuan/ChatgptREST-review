# 2026-04-05 Planning Auto Main-Path Default Walkthrough v1

## What I Changed

I removed another piece of avoidable user decision-making.

Before this batch, many planning requests were already recognized correctly, but
the lane policy still left them in a “manual selection required” state unless
the caller explicitly chose a provider.

I changed that in:

- `chatgptrest/api/routes_agent_v3.py`

Now, once a planning request lands in one of the frozen in-scope planning
profiles, the system automatically exposes a stable main path instead of making
the user think about provider choice.

## What Is Better Now

The practical effect is:

1. workforce planning no longer looks unresolved after profile detection
2. project diagnosis no longer needs a manual provider choice
3. research decision no longer needs a manual provider choice
4. leadership report no longer needs a manual provider choice
5. planning general no longer needs a manual provider choice
6. repo-backed implementation planning still keeps the stronger default:
   - `coding_agent -> codex`

So the user now gets:

- automatic profile selection
- automatic main-path selection
- and then the existing quality-gate / continuity / fail-close behavior

## Evidence

The frozen evidence bundle for this slice is:

- `docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v3/`

The most important new signal in that pack is:

- `stable_planning_profiles_auto_select_main_path = true`

This matters because it moves the product closer to the intended experience:

- describe the work
- let the system choose the normal path
- only intervene when there is a real exception

## Why I Kept It Narrow

I did not touch the front-door scenario matching logic in this slice.

`resolve_scenario_pack` has a very wide blast radius, and GitNexus marks that
area as critical. So I kept this batch narrow:

- do not change profile recognition
- do not change execution-layer scope
- only change the default main path once the profile is already known
