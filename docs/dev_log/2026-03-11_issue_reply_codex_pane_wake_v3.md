# 2026-03-11 Issue Reply Codex Pane Wake v3

## Why v2 Was Still Weak

The watcher already detected new comments and successfully called `tmux send-keys`, but the wake text could still end up sitting in the Codex CLI input composer instead of being submitted.

The practical cause was:

- wake text was multi-line
- multi-line paste into the interactive Codex pane is ambiguous
- the pane could look "woken" at the tmux layer while the message was still only drafted

## v3 Change

`watch_github_issue_replies.py` now wakes the target pane with a stricter sequence:

1. send `Escape`
2. send a **single-line** wake instruction
3. send `C-m`

This keeps the wake prompt out of multi-line draft mode and makes the submit behavior much more reliable.

## Scope

This is still a tmux-pane wake path.

It does **not** turn issue replies into a separate assistant message channel. It just makes the existing "wake the Codex pane" path more deterministic.

## Validation

- [watch_github_issue_replies.py](/vol1/1000/projects/ChatgptREST/ops/watch_github_issue_replies.py)
- [test_watch_github_issue_replies.py](/vol1/1000/projects/ChatgptREST/tests/test_watch_github_issue_replies.py)

Commands:

```bash
./.venv/bin/python -m py_compile ops/watch_github_issue_replies.py tests/test_watch_github_issue_replies.py
./.venv/bin/pytest -q tests/test_watch_github_issue_replies.py
```
