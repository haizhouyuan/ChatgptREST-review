#!/usr/bin/env bash
set -euo pipefail

ROOT="/vol1/1000/projects/ChatgptREST"
OUT_DIR="$ROOT/artifacts/monitor/openclaw_orch"
mkdir -p "$OUT_DIR"

MSG_DEFAULT='请执行一次 ChatgptREST 编排巡查：先核对关键服务与最近异常 jobs，再给出最多 5 条可执行动作。只输出一行 JSON：{"ok":true|false,"summary":"...","actions":[...],"escalate":true|false}。'
MSG="${*:-$MSG_DEFAULT}"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$OUT_DIR/wake_${TS}.json"
ERR="$OUT_DIR/wake_${TS}.err.log"

openclaw agent \
  --agent chatgptrest-orch \
  --session-id chatgptrest-orch-main \
  --message "$MSG" \
  --json \
  --timeout 180 >"$OUT" 2>"$ERR" || {
  echo "[orch] wake failed. see: $ERR" >&2
  exit 2
}

echo "[orch] wake output: $OUT"
echo "[orch] wake stderr: $ERR"
