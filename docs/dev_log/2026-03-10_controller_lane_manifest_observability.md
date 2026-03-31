# 2026-03-10 Controller Lane Manifest Observability

## What changed

- Added a repo-owned manifest for continuity lanes:
  - [`config/controller_lanes.json`](/vol1/1000/projects/ChatgptREST/config/controller_lanes.json)
- Added `sync-manifest` support to [`ops/controller_lane_continuity.py`](/vol1/1000/projects/ChatgptREST/ops/controller_lane_continuity.py)
  - reads the manifest
  - upserts all lanes into `state/controller_lanes.sqlite3`
  - keeps `launch_cmd` / `resume_cmd` empty by default
- Kept continuity in observability-only mode:
  - manifest lanes default to `desired_state="observed"`
  - `sweep` can report them without pretending restart automation is already valid

## Why

- The original continuity implementation had a usable registry, but live state stayed empty because onboarding required manual `upsert-lane` calls.
- Automatic restart is not yet trustworthy for Codex CLI lanes, so the right next step is fleet visibility, not more restart logic.
- A repo-owned manifest gives a stable, reproducible lane inventory for `main/scout/worker-1/verifier`.

## Validation

- `./.venv/bin/pytest -q tests/test_controller_lane_continuity.py`
- `./.venv/bin/python -m py_compile ops/controller_lane_continuity.py`

## Result

- Continuity can now be onboarded reproducibly with one command:
  - `PYTHONPATH=. ./.venv/bin/python ops/controller_lane_continuity.py sync-manifest`
- The registered default lanes are observability-first and do not imply restart authority.
