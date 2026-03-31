# 2026-03-10 OpenClaw Verifier Probe Reply Fallback

## Context

`ops/verify_openclaw_openmind_stack.py` had already been made transcript-aware for
provider fallback rounds, but a live `lean` verifier run still ended with one false
negative:

- `openmind_probe_reply = FAIL`
- `openmind_tool_round = PASS`

The live transcript showed the OpenMind tool was really called and completed, but the
OpenClaw CLI JSON payload returned an empty `result.payloads[0].text` for that round.

## Root Cause

The verifier was still treating the direct CLI payload text as the only success signal
for `openmind_probe_reply`, even when transcript-level tool evidence already proved the
round succeeded.

This mismatch is plausible under provider-fallback / bridged execution:

1. original provider attempt stalls or fails
2. bridge user message continues the same round
3. fallback provider calls the tool and emits the final assistant text in transcript
4. CLI top-level payload text can still be empty

So the failure was in verifier success semantics, not in the OpenMind tool path itself.

## Change

Added `probe_reply_ok(...)` and changed the verifier to accept either:

- exact payload reply match, or
- empty payload text **plus** successful transcript-level tool round

This was applied consistently to:

- `openmind_probe_reply`
- `memory_capture_probe_reply`
- `memory_recall_probe_reply`

## Validation

- `./.venv/bin/pytest -q tests/test_verify_openclaw_openmind_stack.py`
- `./.venv/bin/python -m py_compile ops/verify_openclaw_openmind_stack.py tests/test_verify_openclaw_openmind_stack.py`

Additional live checks during this round confirmed:

- full `pytest -q -x` completed `0`
- the integrated Python app serving `/v2/*` is currently on `127.0.0.1:18711`
- `127.0.0.1:18713` is a separate Node/Express process, not the active OpenMind API
- live `/v2/memory/capture` + `/v2/context/resolve` business smoke succeeds when using:
  - `X-Api-Key`
  - the real integrated host endpoint on `18711`
  - `category=captured_memory` for cross-session remembered-guidance recall

## Practical Note

The live smoke also reconfirmed an important contract detail:

- `captured_memory` is the category that the hot-path cross-session recall lane consumes
- using a custom category like `preference` will still capture successfully, but it will
  not appear in the `Remembered Guidance` block unless the retrieval contract is widened
