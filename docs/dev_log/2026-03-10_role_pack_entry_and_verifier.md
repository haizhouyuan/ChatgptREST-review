# 2026-03-10 Role Pack Entry And Verifier

## What changed

- Exposed role-pack operating instructions in OpenClaw managed workspaces.
  - `scripts/rebuild_openclaw_openmind_stack.py` now writes `ROLE_PACKS.md`
  - `main` workspace docs now explicitly tell the agent to choose `devops` / `research`
  - `maintagent` gets a watchdog-only `ROLE_PACKS.md` instead of a fake specialist role
- Extended `ops/verify_openclaw_openmind_stack.py` to validate live role-pack behavior.
  - capture memory under `roleId=devops`
  - recall that marker with `roleId=devops`
  - verify the same marker is isolated from `roleId=research`
  - include role-pack excerpts/details in review-safe artifacts and markdown output

## Why

- `1A` had already landed in the backend, but role packs were still mostly invisible at the OpenClaw workbench layer.
- The previous verifier only proved generic OpenMind memory capture/recall; it did not prove that role scoping actually worked live.
- This closes the gap between backend plumbing and operator-visible/runtime-verified behavior.

## Validation

- `./.venv/bin/python -m py_compile scripts/rebuild_openclaw_openmind_stack.py ops/verify_openclaw_openmind_stack.py tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py`
- `./.venv/bin/pytest -q tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py`
- `./.venv/bin/pytest -q tests/test_cognitive_api.py -k 'role or kb_hint or captured_memory'`

## Result

- Role packs are now a first-class visible part of the generated `main` workspace.
- The verifier can now prove three things instead of one:
  - generic memory capture/recall works
  - `devops` role memory is retrievable under `devops`
  - the same memory is not leaked into `research`
