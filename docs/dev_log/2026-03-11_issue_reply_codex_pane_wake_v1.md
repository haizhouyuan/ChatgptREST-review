# 2026-03-11 Issue Reply Codex Pane Wake v1

## Goal

Make GitHub issue reply watching capable of waking the **current Codex CLI tmux pane**, not just sending a desktop or webhook notification.

## What Changed

Updated:

- [watch_github_issue_replies.py](/vol1/1000/projects/ChatgptREST/ops/watch_github_issue_replies.py)

Added:

- [watch_issue_and_wake_codex.sh](/vol1/1000/projects/ChatgptREST/ops/watch_issue_and_wake_codex.sh)

## Behavior

`watch_github_issue_replies.py` now supports:

- `--wake-codex-pane`
- `--wake-pane-target <tmux-pane>`
- `--wake-prefix <text>`

When a new issue comment is detected, the watcher:

1. builds the normal alert payload
2. updates the baseline state file
3. sends a natural-language continuation prompt into the target tmux pane with `tmux send-keys`
4. presses Enter, so the Codex CLI session immediately receives a new instruction

The shell wrapper `watch_issue_and_wake_codex.sh` is the convenience entrypoint:

- defaults to `CODEX_CONTROLLER_PANE`
- otherwise falls back to `TMUX_PANE`
- otherwise uses the current tmux pane id
- starts the watcher inside its own tmux session and prints `watch_session/watch_pane/watch_pid/log_file`

## Usage

Watch issue `#112` and wake the current Codex pane on the next reply:

```bash
cd /vol1/1000/projects/ChatgptREST
ops/watch_issue_and_wake_codex.sh 112
```

The wrapper will create or replace tmux session `issue-watch-112`.

Direct Python usage:

```bash
cd /vol1/1000/projects/ChatgptREST
PYTHONPATH=. ./.venv/bin/python ops/watch_github_issue_replies.py 112 \
  --repo haizhouyuan/ChatgptREST \
  --wait \
  --wake-codex-pane \
  --wake-pane-target "$TMUX_PANE"
```

## Validation

```bash
./.venv/bin/python -m py_compile ops/watch_github_issue_replies.py tests/test_watch_github_issue_replies.py
bash -n ops/watch_issue_and_wake_codex.sh
./.venv/bin/pytest -q tests/test_watch_github_issue_replies.py
```

## Note

This is a tmux-pane wake path, not a generic notification path. It assumes the target pane is the interactive Codex CLI session that should resume work on the issue thread.
