# 2026-03-11 Coordination Issue Polling

## Goal

Keep `#114` and `#115` visible without relying on the older watcher flow.

## What changed

Added a standalone polling utility:

- `ops/poll_coordination_issues.py`

It polls a fixed issue list through `gh issue view --json comments`, stores the
last seen snapshot in:

- `state/coordination_issue_poll.json`

and appends comment-count deltas plus latest-comment metadata to:

- `artifacts/monitor/coordination_issue_poll/latest.log`

Optional desktop notifications can be enabled with `--notify`.

## Validation

- `./.venv/bin/pytest -q tests/test_poll_coordination_issues.py`
- `./.venv/bin/python -m py_compile ops/poll_coordination_issues.py tests/test_poll_coordination_issues.py`

## Runtime usage

Foreground one-shot:

```bash
PYTHONPATH=. ./.venv/bin/python ops/poll_coordination_issues.py \
  --issues 114 115 \
  --once
```

Background poll:

```bash
nohup env PYTHONPATH=. ./.venv/bin/python ops/poll_coordination_issues.py \
  --issues 114 115 \
  --interval-seconds 60 \
  >> logs/coordination_issue_poll.out 2>&1 &
```
