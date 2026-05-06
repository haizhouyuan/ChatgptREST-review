# Phase 12 Core Ask Launch Gate Completion Walkthrough v1

## What I Did

- created a gate runner that reads the validation artifacts from Phase 7 to
  Phase 11
- added live health checks against the current API and advisor surfaces
- generated a launch-gate artifact bundle
- kept `public agent MCP` and `strict ChatGPT Pro smoke blocking` outside this
  phase on purpose

## Important Correction

The first draft of the gate misread Phase 8 coverage:

- `phase8 report_v2` uses `num_items=7` and `num_cases=28`
- the gate initially treated `28` as `num_items`
- I corrected the gate to respect `num_cases` where applicable

That was a gate-reader bug, not a regression in the validated surfaces.

## Commands

```bash
./.venv/bin/pytest -q tests/test_core_ask_launch_gate.py tests/test_work_sample_validation.py tests/test_multi_ingress_work_sample_validation.py tests/test_agent_v3_route_work_sample_validation.py tests/test_controller_route_parity_validation.py tests/test_branch_coverage_validation.py -k 'launch_gate or work_sample or route_parity or branch_coverage'
python3 -m py_compile chatgptrest/eval/core_ask_launch_gate.py ops/run_core_ask_launch_gate.py tests/test_core_ask_launch_gate.py
PYTHONPATH=. ./.venv/bin/python ops/run_core_ask_launch_gate.py
```

## Why This Phase Closes The Current Package

Before Phase 12, validation existed, but it was distributed across multiple
 documents and artifact directories. This phase turns those separate greens into
 a single release gate for the current ask path.

That makes it possible to split the next work cleanly:

1. current package: core ask launch gate
2. next package: public agent MCP usability + strict Pro smoke blocking
