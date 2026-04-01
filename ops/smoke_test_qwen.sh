#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

API_URL="${CHATGPTREST_API_URL:-http://127.0.0.1:18711}"

echo "[smoke-qwen] Ensuring Qwen viewer + Chrome are running..."
bash ops/qwen_viewer_start.sh >/dev/null

idem="smoke-qwen-$(date +%Y%m%d-%H%M%S)-$$"
payload='{"kind":"qwen_web.ask","input":{"question":"只输出数字：1+1=?","conversation_url":null},"params":{"preset":"deep_thinking","send_timeout_seconds":120,"wait_timeout_seconds":60,"max_wait_seconds":240,"min_chars":1,"answer_format":"text"}}'

echo "[smoke-qwen] Submitting job..."
job_json="$(
  curl -fsS -X POST "${API_URL}/v1/jobs" \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: ${idem}" \
    -d "${payload}"
)"

job_id="$(
  python3 -c 'import json,sys; obj=json.load(sys.stdin); print(obj.get("job_id") or obj.get("id") or "")' <<<"${job_json}"
)"

if [[ -z "${job_id}" ]]; then
  echo "[smoke-qwen] Failed to parse job_id from response:" >&2
  echo "${job_json}" >&2
  exit 3
fi

echo "[smoke-qwen] job_id=${job_id}"
echo "[smoke-qwen] Waiting..."

final_json="$(
  curl -fsS "${API_URL}/v1/jobs/${job_id}/wait?timeout_seconds=300&poll_seconds=2&auto_wait_cooldown=1"
)"

status="$(
  python3 -c 'import json,sys; obj=json.load(sys.stdin); print((obj.get("status") or "").strip())' <<<"${final_json}"
)"

echo "[smoke-qwen] final status=${status}"
echo "${final_json}"

if [[ "${status}" != "completed" ]]; then
  exit 10
fi

echo "[smoke-qwen] Fetching answer chunk..."
curl -fsS "${API_URL}/v1/jobs/${job_id}/answer?offset=0&max_chars=400" | head -c 800
echo
