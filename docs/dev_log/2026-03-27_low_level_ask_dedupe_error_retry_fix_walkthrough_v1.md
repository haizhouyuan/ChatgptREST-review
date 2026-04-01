# 2026-03-27 low-level ask dedupe error retry fix walkthrough v1

## What happened

The recent-duplicate guard for low-level ask was doing the right high-level thing, but one literal in the SQL filter had drifted from the real state machine.

The code excluded:

- `failed`
- `canceled`

while the real terminal error state is:

- `error`

So a just-failed request remained eligible for duplicate suppression inside the dedupe window.

## Why that is wrong

Duplicate suppression should stop accidental resubmission of an equivalent request that is already active or still meaningfully represented by a recent successful submission.

It should not block a caller from retrying immediately after the previous attempt has already failed.

## What changed

The runtime dedupe query in `chatgptrest/core/ask_guard.py` now excludes:

- `error`
- `canceled`

This aligns the dedupe filter with `chatgptrest/core/state_machine.py`.

## Regression coverage

`tests/test_low_level_ask_guard.py` now includes an explicit retry-after-error scenario for signed `planning-wrapper` low-level asks.

That test keeps the existing “recent active duplicate should still 409” coverage and adds the missing “recent errored duplicate should be allowed to retry” half.
