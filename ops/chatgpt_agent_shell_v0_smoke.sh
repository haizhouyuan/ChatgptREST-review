#!/usr/bin/env bash
set -euo pipefail

# Minimal smoke for ChatGPTAgent v0 shell.
# 1) show session state, 2) run dry-run query, 3) show state.

BASE_URL=${CHATGPTREST_BASE_URL:-http://127.0.0.1:18711}
SESSION_ID=${CHATGPT_AGENT_SESSION_ID:-agent-v0-smoke}
QUESTION=${CHATGPT_AGENT_QUESTION:-请给出一次最小巡检步骤。}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] session status"
python3 "$SCRIPT_DIR/chatgpt_agent_shell_v0.py" --base-url "$BASE_URL" --session-id "$SESSION_ID" --status --json

echo "[2/3] ask (dry-run)"
python3 "$SCRIPT_DIR/chatgpt_agent_shell_v0.py" --base-url "$BASE_URL" --session-id "$SESSION_ID" --question "$QUESTION" --dry-run --json

echo "[3/3] session status"
python3 "$SCRIPT_DIR/chatgpt_agent_shell_v0.py" --base-url "$BASE_URL" --session-id "$SESSION_ID" --status --json
