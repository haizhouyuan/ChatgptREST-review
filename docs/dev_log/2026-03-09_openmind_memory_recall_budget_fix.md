# 2026-03-09 OpenMind Memory Recall Budget Fix

## Why

The new OpenMind memory capture slice was writing durable `captured_memory` records
correctly, but the live OpenClaw verifier still failed the recall half of the flow.

The root cause was not `memory.capture` or transcript parsing. It was a contract
mismatch between the OpenClaw memory plugin and the OpenMind context budget model:

- `openmind-memory` live config was shipping `tokenBudget=2400`
- `ContextAssembler` reserves `system_instruction + user_query + reserve_for_output`
  = `3300` tokens before any context sources fit
- any request under that floor collapses to `policy`-only context

That meant the memory slot could successfully capture durable user preferences and
then immediately fail to recall them in the same live flow.

## What changed

1. `openmind-memory` now treats recall as a memory-first path:
   - default recall sources are `memory + policy`
   - graph retrieval remains on `openmind-graph`
2. `openmind-memory` clamps `tokenBudget` to a minimum of `4000`
3. plugin schema and generated OpenClaw config were aligned to the same minimum
4. the plugin README now documents the memory-first contract
5. source-level and rebuild tests were updated to lock the contract

## Validation

Targeted regression:

```bash
./.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_verify_openclaw_openmind_stack.py \
  tests/test_cognitive_api.py
```

Live rebuild + verifier:

```bash
./.venv/bin/python scripts/rebuild_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --topology lean

systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service

./.venv/bin/python ops/verify_openclaw_openmind_stack.py \
  --state-dir /home/yuanhaizhou/.home-codex-official/.openclaw \
  --expected-topology lean
```

Latest passing lean artifact:

- `artifacts/verify_openclaw_openmind/20260309T134238Z/verify_openclaw_openmind_stack.json`
- `artifacts/verify_openclaw_openmind/20260309T134238Z/verify_openclaw_openmind_stack.md`

## Result

The live `lean` topology now passes the full memory vertical slice:

- `openmind_memory_capture`
- durable episodic promotion + audit trail
- `openmind_memory_recall`
- `Remembered Guidance` block present in prompt-safe context
- marker text present in returned memory block
