#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"
mkdir -p artifacts/kimi_smoke

kimicode --help > artifacts/kimi_smoke/kimicode_help.txt 2>&1 || true

if timeout 120s kimicode --print \
  --work-dir "$PWD" \
  --afk -y \
  --max-steps-per-turn 2 \
  --mcp-config-file contracts/kimi_mcp_none.json \
  -p "Create exactly one JSON file at artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json. Do not access live finance data. Do not modify any other file. The JSON must include issue_id FINBOT-ENG-002, status pass, runtime kimicode, mcp_profile none, created_by_native_kimi true, finbot_execution false, paperclip_apply false, files_created containing artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json." \
  > artifacts/kimi_smoke/stdout.txt \
  2> artifacts/kimi_smoke/stderr.txt; then
  python3 tools/validate_kimi_smoke_result.py artifacts/kimi_smoke/KIMI_SMOKE_RESULT.json
else
  python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/kimi_smoke/KIMI_SMOKE_BLOCKED.json")
data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
data.update({
  "issue_id": "FINBOT-ENG-002",
  "status": "blocked",
  "reason": "kimi_no_mcp_smoke_failed_or_timeout",
  "mcp_profile": "none",
  "stdout_path": "artifacts/kimi_smoke/stdout.txt",
  "stderr_path": "artifacts/kimi_smoke/stderr.txt",
  "help_path": "artifacts/kimi_smoke/kimicode_help.txt",
  "finbot_execution": False,
  "paperclip_apply": False
})
out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  exit 1
fi

