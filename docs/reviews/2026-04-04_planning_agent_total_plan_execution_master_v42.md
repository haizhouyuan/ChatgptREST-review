# 2026-04-04 Planning Agent Total Plan Execution Master v42

## This version changes

This version freezes the `Gemini blank-zombie idempotency recovery narrowed to runtime-mismatch + legacy-schema migration coverage` batch.

## Newly completed in v42

Completed:

- removed the unsafe broad Gemini wait root-flap downgrade before commit
- added `runtime_instance_id`-based blank idempotency recovery in `chatgpt_web_mcp/idempotency.py`
- made same-runtime blank rows and non-`chatgptrest:` blank rows fail closed
- added explicit legacy-schema migration coverage for old idempotency DBs without `runtime_instance_id`
- re-ran targeted Gemini idempotency/wait tests successfully

## Program state after v42

What is now clearer:

- the earlier `blank in_progress zombie replay` failure mode has a narrower and materially safer repair path
- the previous red-team `reject` for this batch was valid and has been addressed before commit
- `W1` is now less blocked by idempotency corruption and more clearly blocked by live provider/runtime stability

## What v42 still does not claim

This version still does **not** claim:

- live OpenClawBot completion is green
- Gemini send/bootstrap stability is green
- phase-1 is complete
- Feishu/OpenClawBot conversational ingress is fully proven end-to-end

## Current nearest-next work

After v42, the next useful work should still stay inside `W1` and narrow to one question:

1. why is the current OpenClaw live provider path still producing `CDP connect failed (TargetClosedError ...)` cooldown behavior on `gemini_web.ask` for the latest live run?
