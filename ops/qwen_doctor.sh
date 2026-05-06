#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "[qwen-doctor] Ensuring Qwen viewer + Chrome are running..."
bash ops/qwen_viewer_start.sh >/dev/null

if curl -fsS "http://127.0.0.1:9335/json/version" >/dev/null; then
  echo "[qwen-doctor] CDP OK: http://127.0.0.1:9335"
else
  echo "[qwen-doctor] CDP not reachable: http://127.0.0.1:9335" >&2
  exit 2
fi

viewer_host=""
if [[ -f ".run/qwen_viewer/novnc_bind_host.txt" ]]; then
  viewer_host="$(cat ".run/qwen_viewer/novnc_bind_host.txt" 2>/dev/null || true)"
fi
viewer_host="$(echo "${viewer_host}" | tr -d '\r' | xargs || true)"
if [[ -n "${viewer_host}" ]]; then
  echo "[qwen-doctor] noVNC: http://${viewer_host}:6085/vnc.html"
fi

echo "[qwen-doctor] Running qwen_web_self_check (driver)..."
./.venv/bin/python - <<'PY'
import asyncio
from chatgpt_web_mcp.providers import qwen_web

async def main():
    res = await qwen_web.qwen_web_self_check(timeout_seconds=20)
    print(res)

asyncio.run(main())
PY

