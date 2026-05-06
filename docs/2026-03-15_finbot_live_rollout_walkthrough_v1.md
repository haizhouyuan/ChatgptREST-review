# Finbot Live Rollout Walkthrough v1

## Goal

Deploy `finbot` as the OpenClaw investment-research scout, then prove three things with live checks:

1. `finbot` is actually present in live OpenClaw state
2. `finbot` can run its deterministic `finagent`-backed helper commands
3. `finbot` can resurface previously researched opportunities and support parallel theme work

## Live rollout steps

### 1. Rebuild OpenClaw state

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  scripts/rebuild_openclaw_openmind_stack.py \
  --state-dir ~/.openclaw \
  --topology ops
```

Observed result:

- `agents.list` became `main + maintagent + finbot`
- legacy `chatgptrest-*` orch/guardian agent dirs were pruned from the state dir
- codex auth sync ran for `main`, `maintagent`, and `finbot`

### 2. Confirm live finbot state

Hard checks:

- `~/.openclaw/openclaw.json` includes `finbot`
- `~/.openclaw/agents/finbot/agent/` exists
- `openclaw sandbox explain --agent finbot --json` reports:
  - `"mode": "all"`
  - `"scope": "agent"`
  - `"workspaceAccess": "rw"`
  - `"sessionIsSandboxed": true`

### 3. Smoke-test finbot helper commands

```bash
python3 ops/openclaw_finbot.py dashboard-refresh --format json
python3 ops/openclaw_finbot.py watchlist-scout --format json --scope today --limit 8
python3 ops/openclaw_finbot.py inbox-list --format json --limit 20
```

## What live finbot discovered

`watchlist-scout` produced a new pending inbox item:

- `item_id`: `finbot-watchlist-transformer-supercycle-c1afcf56d7a2`
- title: `Finbot scout · 变压器超级周期 — AI+新能源+电网更新三重驱动`
- summary:
  - `tc_transformer_tbea → starter`
  - queue pressure:
    - `decision_maintenance: 11`
    - `review_remediation: 23`
  - catalyst:
    - `特变电工半年报(8月)`

This is a real rediscovery of an already researched opportunity, not a synthetic test case.

## Parallel theme runs executed after rollout

Using `finagent` as the research engine behind `finbot`, the following theme suites were rerun in parallel:

### Transformer

Run root:

- `/vol1/1000/projects/finagent/artifacts/theme_runs/2026-03-15_transformer_finbot_live`

Result:

- `recommended_posture = watch_with_prepare_candidate`
- best expression:
  - `中国西电`
  - `UHV 一次设备 + 电力电子`

### Memory bifurcation

Run root:

- `/vol1/1000/projects/finagent/artifacts/theme_runs/2026-03-15_memory_bifurcation_finbot_live`

Result:

- `recommended_posture = watch_with_prepare_candidate`
- best expression:
  - `SK Hynix`
  - `HBM franchise`

### Silicon photonics

Run root:

- `/vol1/1000/projects/finagent/artifacts/theme_runs/2026-03-15_silicon_photonics_finbot_live`

Result:

- `recommended_posture = watch_with_prepare_candidate`
- best expression:
  - `中际旭创`
  - `800G / 1.6T 光模块`

## Validation that passed

- `pytest -q tests/test_finbot.py tests/test_rebuild_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py`
- `openclaw sandbox explain --agent finbot --json`
- `openclaw health --json`
- `python3 ops/openclaw_finbot.py dashboard-refresh --format json`
- `python3 ops/openclaw_finbot.py watchlist-scout --format json --scope today --limit 8`
- three parallel `finagent` theme suite reruns

## Validation that is still imperfect

Full:

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/verify_openclaw_openmind_stack.py \
  --state-dir ~/.openclaw \
  --expected-topology ops
```

still timed out in `advisor_auth_probe()` on local HTTP auth probing.

That does **not** invalidate the finbot rollout itself, because the finbot-specific checks passed, but it means the full-stack verifier still has an environment-specific timeout path that should be debugged separately.

## Bottom line

`finbot` is now live in OpenClaw state, sandboxed, and able to drive real `finagent` workflows. It has already:

- written a live watchlist inbox item
- resurfaced an already researched transformer opportunity
- supported parallel reruns for transformer, memory, and silicon-photonics themes
