# 2026-03-11 Issue Reply Wake Submit Delay and Poller Wake

## Why

The coordination reply watchers could detect GitHub comment deltas, but pane wake-up was still unreliable in practice:

- one pane received the text, but the message stayed drafted in the Codex composer
- pressing Enter too early could behave like a newline instead of a submit
- the background coordination poller could log deltas, but could not use the same wake path
- sending `Escape` first could interrupt or cancel the active Codex session instead of just clearing draft input

## What Changed

### `ops/watch_github_issue_replies.py`

The tmux wake sequence is now:

1. send the wake text literally
2. wait for a short submit delay
3. send `C-m`

The submit delay is configurable via:

- `--wake-submit-delay-seconds`

### `ops/poll_coordination_issues.py`

The background coordination poller now supports the same optional pane wake path:

- `--wake-codex-pane`
- `--wake-pane-target`
- `--wake-prefix`
- `--wake-submit-delay-seconds`

This keeps watcher-based and poller-based wake behavior on one code path.

## Validation

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_watch_github_issue_replies.py \
  tests/test_poll_coordination_issues.py

PYTHONPATH=. ./.venv/bin/python -m py_compile \
  ops/watch_github_issue_replies.py \
  ops/poll_coordination_issues.py \
  tests/test_watch_github_issue_replies.py \
  tests/test_poll_coordination_issues.py
```

## Scope

This change only hardens coordination wake-up behavior.

It does not:

- change runtime execution telemetry
- change EvoMap ingestion
- change planning/runtime cutover behavior
