#!/usr/bin/env bash
set -euo pipefail

ROOT="/vol1/1000/projects/ChatgptREST"
cd "$ROOT"

ISSUE_NUMBER="${1:-}"
if [[ -z "$ISSUE_NUMBER" ]]; then
  echo "usage: $0 <issue_number> [repo]" >&2
  exit 2
fi

REPO="${2:-haizhouyuan/ChatgptREST}"
TARGET_PANE="${CODEX_CONTROLLER_PANE:-${TMUX_PANE:-}}"
if [[ -z "${TARGET_PANE}" ]]; then
  TARGET_PANE="$(tmux display-message -p '#{pane_id}')"
fi

TS="$(date +%Y%m%dT%H%M%S)"
OUT_DIR="$ROOT/artifacts/monitor/github_issue_watch"
mkdir -p "$OUT_DIR"
LOG_FILE="$OUT_DIR/issue_${ISSUE_NUMBER}_watch_${TS}.log"
SESSION_NAME="issue-watch-${ISSUE_NUMBER}"

PREFIX="A new GitHub issue reply is waiting in ${REPO}#${ISSUE_NUMBER}."
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
fi

tmux new-session -d -s "$SESSION_NAME" \
  "cd '$ROOT' && CODEX_CONTROLLER_PANE='$TARGET_PANE' ./.venv/bin/python ops/watch_github_issue_replies.py '$ISSUE_NUMBER' --repo '$REPO' --wait --wake-codex-pane --wake-current-if-unseen --wake-pane-target '$TARGET_PANE' --wake-prefix '$PREFIX' >'$LOG_FILE' 2>&1"

WATCH_PANE="$(tmux list-panes -t "$SESSION_NAME" -F '#{pane_id}' | head -n 1)"
WATCH_PID="$(tmux list-panes -t "$SESSION_NAME" -F '#{pane_pid}' | head -n 1)"
SESSION_FILE="$OUT_DIR/issue_${ISSUE_NUMBER}_watch.session"
printf '%s\n' "$SESSION_NAME" >"$SESSION_FILE"

echo "{\"ok\":true,\"issue_number\":${ISSUE_NUMBER},\"repo\":\"${REPO}\",\"target_pane\":\"${TARGET_PANE}\",\"watch_session\":\"${SESSION_NAME}\",\"watch_pane\":\"${WATCH_PANE}\",\"watch_pid\":${WATCH_PID},\"log_file\":\"${LOG_FILE}\",\"session_file\":\"${SESSION_FILE}\"}"
