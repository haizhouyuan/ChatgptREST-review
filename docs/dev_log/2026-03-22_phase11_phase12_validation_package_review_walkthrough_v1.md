# Phase 11 / Phase 12 Validation Package Review Walkthrough v1

## What I Checked

- inspected the Phase 11 validator, dataset, tests, and generated report
- inspected the Phase 12 gate implementation, runner, docs, and generated report
- re-ran the exact pytest subsets provided for both phases
- re-ran both validation runners
- probed live health and a low-risk unauthenticated `/v3/agent/turn` request

## Commands

```bash
./.venv/bin/pytest -q tests/test_branch_coverage_validation.py tests/test_routes_agent_v3.py tests/test_controller_engine_planning_pack.py -k 'branch_coverage or clarify or kb_direct or team_fallback or no_pack'
./.venv/bin/pytest -q tests/test_core_ask_launch_gate.py tests/test_work_sample_validation.py tests/test_multi_ingress_work_sample_validation.py tests/test_agent_v3_route_work_sample_validation.py tests/test_controller_route_parity_validation.py tests/test_branch_coverage_validation.py -k 'launch_gate or work_sample or route_parity or branch_coverage'
PYTHONPATH=. ./.venv/bin/python ops/run_branch_coverage_validation.py
PYTHONPATH=. ./.venv/bin/python ops/run_core_ask_launch_gate.py
python3 - <<'PY'
import urllib.request
req = urllib.request.Request('http://127.0.0.1:18711/healthz', method='GET')
with urllib.request.urlopen(req, timeout=5) as r:
    print(r.status)
    print(r.read().decode())
PY
python3 - <<'PY'
import json, urllib.request
body = {'message': '请总结面试纪要', 'goal_hint': 'planning', 'delivery_mode': 'sync'}
req = urllib.request.Request(
    'http://127.0.0.1:18711/v3/agent/turn',
    data=json.dumps(body).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
with urllib.request.urlopen(req, timeout=20) as r:
    print(r.status)
    print(r.read().decode())
PY
```

## Results

- Phase 11 pytest subset: passed
- Phase 12 pytest subset: passed
- `ops/run_branch_coverage_validation.py`: `items=4 passed=4 failed=0`
- `ops/run_core_ask_launch_gate.py`: `overall_passed=True`
- live `GET /healthz`: `200`
- unauthenticated live `POST /v3/agent/turn`: `401`

## Why I Narrowed Phase 12

The code clearly shows that Phase 12 is a reader over prior validation artifacts
plus health checks. That is useful and valid, but it is not the same thing as a
fresh replay gate or an authenticated live ask canary.

So my final position is:

- Phase 11: pass as written
- Phase 12: pass with narrowed interpretation
