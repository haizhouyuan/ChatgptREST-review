# 2026-04-04 Codex 5.4 xhigh Redteam Gemini Idempotency Runtime Mismatch Recovery v1

## Scope reviewed

Reviewed batch:

- `chatgpt_web_mcp/idempotency.py`
- `tests/test_driver_idempotency_upload_hash.py`

## First red-team verdict

Initial verdict was `reject`.

High findings in the first pass:

- age-only blank `in_progress` recovery could replay same-process queued Gemini asks that were still waiting behind `_ask_lock()`
- the new Gemini wait root-flap helper could convert true thread-loss situations into repeated `in_progress` requeues

## Actions taken after the first rejection

- reverted the Gemini wait helper and its isolated test
- redesigned blank-row recovery to require runtime mismatch instead of age alone
- kept blank-row recovery only for `chatgptrest:*` keys
- made non-`chatgptrest:` blank rows fail closed
- added legacy-schema migration coverage

## Second red-team position

The narrowed batch reached `approve-with-fixes`.

Remaining medium concerns after narrowing:

- `runtime_instance_id` is process-scoped, so overlapping live writers against the same idempotency DB remain an unsupported boundary
- legacy-schema migration needed explicit coverage, which was then added in this batch before commit

## Independent takeaway

Red-team review no longer blocks commit of this narrowed batch.

The batch is acceptable as a safe narrowing of the blank-zombie recovery path, but it does not solve the separate live OpenClaw/Gemini provider stability issues that still remain in `W1`.
