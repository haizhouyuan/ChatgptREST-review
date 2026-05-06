#!/usr/bin/env bash
set -euo pipefail

ROOT="/vol1/1000/projects/ChatgptREST"
OUT_DIR="$ROOT/artifacts/monitor/openclaw_guardian"
mkdir -p "$OUT_DIR"
export OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-/home/yuanhaizhou/.home-codex-official/.openclaw}"
OPENCLAW_BIN="${OPENCLAW_CMD:-/home/yuanhaizhou/.home-codex-official/.local/bin/openclaw}"
AGENT_ID="chatgptrest-guardian"
SESSION_ID="chatgptrest-guardian-main"
if [[ ! -d "$OPENCLAW_STATE_DIR/agents/$AGENT_ID" && -d "$OPENCLAW_STATE_DIR/agents/main" ]]; then
  AGENT_ID="main"
fi

MSG_DEFAULT='请执行一次托管巡查：检查 /healthz、/v1/ops/status、最近异常 jobs、policy violation（Pro短提示词），并只输出一行JSON：{"resolved":true|false,"summary":"...","actions":[...],"unresolved":[...]}。'
MSG="${*:-$MSG_DEFAULT}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$OUT_DIR/wake_${TS}.json"
ERR="$OUT_DIR/wake_${TS}.err.log"

"$OPENCLAW_BIN" agent \
  --agent "$AGENT_ID" \
  --session-id "$SESSION_ID" \
  --message "$MSG" \
  --json \
  --timeout 180 >"$OUT" 2>"$ERR" || {
  echo "[guardian] wake failed. see: $ERR" >&2
  exit 2
}

echo "[guardian] wake output: $OUT"
echo "[guardian] wake stderr: $ERR"
