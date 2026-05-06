# Unified Release Gate Pack Implementation V1

Date: 2026-04-08

## Scope

This change implements Work Package 4 of the next-stage plan:

- define a single manifest-driven release gate pack
- wire the four stage-defining gates
- keep the pack narrow and evidence-oriented

It does **not** broaden the release pack into a generic platform readiness suite.

## What was added

### 1. Checked-in manifest

- [next_stage_release_gate_pack_manifest_v1.json](/vol1/1000/projects/ChatgptREST/ops/next_stage_release_gate_pack_manifest_v1.json)

The manifest freezes the four gates for this stage:

1. `coding_agent_v1`
2. `openclaw_entry_policy`
3. `authority_precedence`
4. `promotion_maintenance_safety`

Each gate declares the commands that must pass for the release pack to stay green.

### 2. Manifest-driven runner

- [run_next_stage_release_gate_pack.py](/vol1/1000/projects/ChatgptREST/ops/run_next_stage_release_gate_pack.py)

The runner:

- loads the checked-in manifest
- creates a timestamped run directory under `artifacts/monitor/next_stage_release_gate_pack/`
- executes every gate command with captured `stdout` / `stderr`
- writes per-command JSON records
- writes per-gate manifests
- writes a top-level `summary.json` and `summary.md`
- returns non-zero if any gate fails

### 3. Deterministic runner tests

- [test_run_next_stage_release_gate_pack.py](/vol1/1000/projects/ChatgptREST/tests/test_run_next_stage_release_gate_pack.py)

The tests verify:

- the runner writes complete per-gate and top-level artifacts when all commands pass
- the runner still writes a full report when one gate fails

## Why this shape

This stage needed a **single release-blocking evidence plane**.

The manifest-driven runner keeps the stage narrow:

- coding-agent contract stays contract-tested
- OpenClaw entry policy stays contract-tested
- authority precedence stays structurally scanned and tested
- promotion maintenance stays refresh-only and evidence-producing

It avoids two failure modes:

1. scattering release checks across unrelated scripts without one authoritative summary
2. regrowing a broad “platform launch gate” instead of the narrow boundary-consolidation gate required by the current program

## Acceptance target for this implementation

This implementation is correct if:

1. the runner can execute all four gates from one manifest
2. each gate writes durable command logs and a per-gate manifest
3. the top-level summary clearly reports pass/fail counts
4. a failed gate still leaves a complete evidence pack behind

## Follow-on work

After this implementation lands, the next immediate step is to run the gate pack against the repo/runtime and write the release evidence summary.
