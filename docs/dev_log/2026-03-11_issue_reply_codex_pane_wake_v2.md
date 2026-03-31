# 2026-03-11 Issue Reply Codex Pane Wake v2

## Why v2

The `v1` watcher could wake the Codex tmux pane when a **future** issue reply arrived, but it still missed one practical case:

- if the watcher was started **after** another agent had already posted the latest reply
- and there was no existing watcher state file yet
- the watcher treated that latest reply as baseline and did not wake the pane

That is exactly what happened on issue `#112`.

## Fix

`watch_github_issue_replies.py` now supports:

- `--wake-current-if-unseen`

Behavior:

- if there is no prior state file
- and the tracked issue already has a latest comment
- the watcher can immediately treat that latest comment as a wake event
- then it writes the baseline and continues waiting for future comments

The wrapper [watch_issue_and_wake_codex.sh](/vol1/1000/projects/ChatgptREST/ops/watch_issue_and_wake_codex.sh) now enables this mode by default.

## Result

The watcher semantics are now:

- first start: wake once on the current latest reply if one already exists
- after that: wake again only on strictly newer replies

This matches the practical coordination need for GitHub issue based multi-agent handoff.

## Validation

```bash
./.venv/bin/python -m py_compile ops/watch_github_issue_replies.py tests/test_watch_github_issue_replies.py
./.venv/bin/pytest -q tests/test_watch_github_issue_replies.py
```

The test suite now includes a first-run wake case.

