#!/usr/bin/env bash
set -euo pipefail

# Send a periodic reminder to a tmux pane.
# Note: send the text first, wait 5s, then send Enter (C-m).

TARGET="${CODEX_CONTROLLER_PANE:-}"
if [[ -z "${TARGET}" ]]; then
  TARGET="$(tmux display-message -p '#{session_name}:#{window_index}.#{pane_index}')"
fi

INTERVAL_SECONDS="${1:-1200}"   # 20 minutes
DURATION_SECONDS="${2:-10800}"  # 3 hours

end_ts=$((SECONDS + DURATION_SECONDS))
while (( SECONDS < end_ts )); do
  tmux send-keys -t "${TARGET}" "echo \"[REMINDER] ChatgptREST monitor is running; check /vol1/1000/projects/ChatgptREST/artifacts/monitor/ for logs and handle blocked/cooldown if any.\""
  sleep 5
  tmux send-keys -t "${TARGET}" C-m
  sleep "${INTERVAL_SECONDS}"
done

