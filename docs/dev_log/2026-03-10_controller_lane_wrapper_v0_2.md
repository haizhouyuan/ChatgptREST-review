# 2026-03-10 Controller Lane Wrapper v0.2

## Why

`controller_lane_continuity` had already been downgraded to observability-first,
but the fleet still showed empty summaries because real lane commands were not
heartbeating into the registry. This change adds a thin wrapper so actual lane
commands can participate in:

- `lane.heartbeat`
- `lane.reported`
- digest/status visibility

without claiming automatic restart or second-controller semantics.

## What changed

- Added [`ops/controller_lane_wrapper.py`](/vol1/1000/projects/ChatgptREST/ops/controller_lane_wrapper.py)
  - requires a pre-registered lane
  - launches one command
  - sends periodic `working` heartbeats
  - reports `completed`/`failed` with exit code and optional artifact path
- Added [`tests/test_controller_lane_wrapper.py`](/vol1/1000/projects/ChatgptREST/tests/test_controller_lane_wrapper.py)
  - success path with artifact
  - failure path with non-zero exit code

## Operational stance

- continuity remains **observability-only**
- `launch_cmd` / `resume_cmd` are still optional and not required for wrapper use
- real lane automation should call the wrapper instead of relying on bare
  `codex exec ... -`

## Example

```bash
PYTHONPATH=. ./.venv/bin/python ops/controller_lane_wrapper.py \
  --lane-id verifier \
  --summary "role pack smoke" \
  --artifact-path /tmp/verifier.json \
  -- ./.venv/bin/pytest -q tests/test_role_pack.py
```
