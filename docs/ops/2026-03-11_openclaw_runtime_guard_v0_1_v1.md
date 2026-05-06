# OpenClaw Runtime Guard v0.1

Date: 2026-03-11

## Scope

This is an observe-first sidecar for `#120`.

It does not replace `main`, does not change retrieval defaults, and does not
promote runtime telemetry into active knowledge.

Current scope is Phase 0 + Phase 1 only:

- freeze the detector input/output contract
- scan existing EventBus / controller lane / EvoMap state
- emit artifacts and operator digest
- no self-heal, no policy mutation, no controller behavior

## Files

- `ops/openclaw_runtime_guard.py`
- `ops/run_openclaw_runtime_guard_smoke.py`
- `ops/systemd/chatgptrest-openclaw-runtime-guard.service`
- `ops/systemd/chatgptrest-openclaw-runtime-guard.timer`

## Detector Set

The first release only evaluates six deterministic detectors:

1. `missing_heartbeat`
2. `started_without_terminal`
3. `tool_failure_spike`
4. `telemetry_contract_violation`
5. `planning_opt_in_zero_hit`
6. `evomap_runtime_visibility_regression`

## Artifact Contract

Each run writes a timestamped bundle under:

- `artifacts/monitor/runtime_guard/<ts>/`

Required files:

- `state_summary.json`
- `incident_summary.json`
- `detector_hits.json`
- `runtime_guard_latest.md`

Convenience pointers:

- `artifacts/monitor/runtime_guard/latest.json`
- `artifacts/monitor/runtime_guard/latest.md`

Exit codes:

- `0`: no detector hit
- `2`: one or more detector hits
- `1`: runner failure

## Manual Run

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/openclaw_runtime_guard.py \
  --base-url http://127.0.0.1:18711
```

Synthetic smoke:

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/run_openclaw_runtime_guard_smoke.py
```

## Configuration

Important inputs:

- `OPENMIND_EVENTS_DB` or `OPENMIND_EVENTBUS_DB`
- `EVOMAP_KNOWLEDGE_DB`
- `CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR`
- `CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_ROOT`
- `CHATGPTREST_OPS_TOKEN` or `CHATGPTREST_API_TOKEN`

If `CHATGPTREST_PLANNING_RUNTIME_PACK_BUNDLE_DIR` is not set, the planning
opt-in detector stays disabled instead of inventing activation state.

## systemd

Install user units:

```bash
cd /vol1/1000/projects/ChatgptREST
bash ops/systemd/install_user_units.sh
systemctl --user enable --now chatgptrest-openclaw-runtime-guard.timer
```

Inspect:

```bash
systemctl --user status chatgptrest-openclaw-runtime-guard.service
systemctl --user list-timers | rg runtime-guard
```

The service intentionally treats exit code `2` as success so detector hits do
not flip the unit into failed state.
