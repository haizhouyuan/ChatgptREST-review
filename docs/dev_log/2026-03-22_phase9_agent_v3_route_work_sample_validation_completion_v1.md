# Phase 9 Agent V3 Route Work Sample Validation Completion v1

## Result

Phase 9 completed.

This phase adds a dedicated route-level validation pack for the public
[`/v3/agent/turn`](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
surface and confirms that representative `planning/research` asks still land on
the intended public route outcomes.

## Deliverables

- Pack spec:
  - [2026-03-22_phase9_agent_v3_route_work_sample_validation_pack_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-22_phase9_agent_v3_route_work_sample_validation_pack_v1.md)
- Eval module:
  - [agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/agent_v3_route_work_sample_validation.py)
- Dataset:
  - [phase9_agent_v3_route_work_samples_v1.json](/vol1/1000/projects/ChatgptREST/eval_datasets/phase9_agent_v3_route_work_samples_v1.json)
- Runner:
  - [run_agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_agent_v3_route_work_sample_validation.py)
- Tests:
  - [test_agent_v3_route_work_sample_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_agent_v3_route_work_sample_validation.py)
- Artifacts:
  - [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase9_agent_v3_route_work_sample_validation_20260322/report_v1.json)
  - [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase9_agent_v3_route_work_sample_validation_20260322/report_v1.md)

## Verification

Executed:

```bash
./.venv/bin/pytest -q tests/test_agent_v3_route_work_sample_validation.py tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py -k 'agent_v3_route or planning or research or clarify or business_planning or research_report'
python3 -m py_compile chatgptrest/eval/agent_v3_route_work_sample_validation.py ops/run_agent_v3_route_work_sample_validation.py tests/test_agent_v3_route_work_sample_validation.py
PYTHONPATH=. ./.venv/bin/python ops/run_agent_v3_route_work_sample_validation.py
```

Outcome:

- dataset: `phase9_agent_v3_route_work_samples_v1`
- items: `7`
- passed: `7`
- failed: `0`

## Scope Freeze

Phase 9 proves:

- `/v3/agent/turn` route-level replay remains stable for representative
  `planning/research` asks
- clarify-vs-controller branch selection remains stable for these business samples
- public response `status` and `provenance.route` remain aligned with current
  scenario-pack policy

Phase 9 does **not** prove:

- OpenClaw dynamic replay
- full-stack artifact / knowledge writeback correctness
- downstream controller runtime quality

