#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${ROOT_DIR}/.run"
RUN_DIR="${ROOT_DIR}/.run/qwen_chrome"
mkdir -p "${RUN_DIR}"

DISPLAY="${DISPLAY:-:99}"
QWEN_CHROME_USER_DATA_DIR="${QWEN_CHROME_USER_DATA_DIR:-${ROOT_DIR}/secrets/qwen-chrome-profile}"
QWEN_CHROME_DEBUG_PORT="${QWEN_CHROME_DEBUG_PORT:-9335}"
QWEN_CHROME_START_URL="${QWEN_CHROME_START_URL:-https://www.qianwen.com/}"
QWEN_CHROME_WINDOW_SIZE="${QWEN_CHROME_WINDOW_SIZE:-1920,1080}"
QWEN_CHROME_WINDOW_POSITION="${QWEN_CHROME_WINDOW_POSITION:-0,0}"
QWEN_CHROME_NO_SANDBOX="${QWEN_CHROME_NO_SANDBOX:-1}"
QWEN_CHROME_DISABLE_DEV_SHM_USAGE="${QWEN_CHROME_DISABLE_DEV_SHM_USAGE:-1}"
QWEN_CHROME_DISABLE_GPU="${QWEN_CHROME_DISABLE_GPU:-1}"
QWEN_CHROME_DISABLE_SESSION_CRASHED_BUBBLE="${QWEN_CHROME_DISABLE_SESSION_CRASHED_BUBBLE:-1}"
QWEN_CHROME_CDP_READY_TRIES="${QWEN_CHROME_CDP_READY_TRIES:-80}"
QWEN_CHROME_CDP_READY_DELAY_SECONDS="${QWEN_CHROME_CDP_READY_DELAY_SECONDS:-0.1}"
QWEN_CHROME_EXTRA_ARGS="${QWEN_CHROME_EXTRA_ARGS:-}"
if [[ -z "${QWEN_CHROME_EXTRA_ARGS}" && "${QWEN_CHROME_DISABLE_GPU}" == "1" ]]; then
  QWEN_CHROME_EXTRA_ARGS="--use-gl=swiftshader --enable-unsafe-swiftshader"
fi

PID_FILE="${ROOT_DIR}/.run/qwen_chrome.pid"
LOG_FILE="${RUN_DIR}/chrome.log"

port_open() {
  local host="$1"
  local port="$2"
  python3 - "${host}" "${port}" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(0.2)
try:
  rc = sock.connect_ex((host, port))
  raise SystemExit(0 if rc == 0 else 1)
finally:
  sock.close()
PY
}

wait_for_port() {
  local host="$1"
  local port="$2"
  local tries="${3:-80}"
  local delay_seconds="${4:-0.1}"

  for _ in $(seq 1 "${tries}"); do
    if port_open "${host}" "${port}"; then
      return 0
    fi
    sleep "${delay_seconds}"
  done
  return 1
}

cdp_ready() {
  local host="$1"
  local port="$2"
  python3 - "${host}" "${port}" <<'PY'
import json
import sys
import urllib.request

host = sys.argv[1]
port = int(sys.argv[2])
url = f"http://{host}:{port}/json/version"
try:
    with urllib.request.urlopen(url, timeout=0.5) as resp:
        data = json.load(resp)
    ws = str((data or {}).get("webSocketDebuggerUrl") or "").strip()
    raise SystemExit(0 if ws else 1)
except Exception:
    raise SystemExit(1)
PY
}

wait_for_cdp_ready() {
  local host="$1"
  local port="$2"
  local tries="${3:-80}"
  local delay_seconds="${4:-0.1}"

  for _ in $(seq 1 "${tries}"); do
    if cdp_ready "${host}" "${port}"; then
      return 0
    fi
    sleep "${delay_seconds}"
  done
  return 1
}

rm_stale_pidfile() {
  [[ -f "${PID_FILE}" ]] || return 0
  local pid
  pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
    rm -f "${PID_FILE}"
  fi
}

rm_stale_pidfile

if [[ -f "${PID_FILE}" ]]; then
  pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null && port_open 127.0.0.1 "${QWEN_CHROME_DEBUG_PORT}"; then
    echo "Qwen Chrome already running (pid=${pid})."
    echo "  cdp=http://127.0.0.1:${QWEN_CHROME_DEBUG_PORT}"
    exit 0
  fi
fi

if port_open 127.0.0.1 "${QWEN_CHROME_DEBUG_PORT}"; then
  echo "CDP port already open on 127.0.0.1:${QWEN_CHROME_DEBUG_PORT} (another Chrome instance may be running)."
  echo "  cdp=http://127.0.0.1:${QWEN_CHROME_DEBUG_PORT}"
  exit 0
fi

mkdir -p "${QWEN_CHROME_USER_DATA_DIR}"

args=(
  --user-data-dir="${QWEN_CHROME_USER_DATA_DIR}"
  --remote-debugging-address=127.0.0.1
  --remote-debugging-port="${QWEN_CHROME_DEBUG_PORT}"
  --disable-blink-features=AutomationControlled
  --disable-infobars
  --no-first-run
  --no-default-browser-check
  --password-store=basic
  --window-size="${QWEN_CHROME_WINDOW_SIZE}"
  --window-position="${QWEN_CHROME_WINDOW_POSITION}"
  --no-proxy-server
)

if [[ "${QWEN_CHROME_NO_SANDBOX}" == "1" ]]; then
  args+=(--no-sandbox)
fi
if [[ "${QWEN_CHROME_DISABLE_DEV_SHM_USAGE}" == "1" ]]; then
  args+=(--disable-dev-shm-usage)
fi
if [[ "${QWEN_CHROME_DISABLE_GPU}" == "1" ]]; then
  args+=(--disable-gpu)
fi
if [[ "${QWEN_CHROME_DISABLE_SESSION_CRASHED_BUBBLE}" == "1" ]]; then
  args+=(--disable-session-crashed-bubble)
fi
if [[ -n "${QWEN_CHROME_EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  args+=(${QWEN_CHROME_EXTRA_ARGS})
fi

export DISPLAY
export HOME="${HOME:-/home/yuanhaizhou}"

echo "Starting Qwen Chrome:"
echo "  DISPLAY=${DISPLAY}"
echo "  user-data-dir=${QWEN_CHROME_USER_DATA_DIR}"
echo "  cdp=http://127.0.0.1:${QWEN_CHROME_DEBUG_PORT}"
echo "  no_proxy_server=1"
echo "  log=${LOG_FILE}"

setsid google-chrome "${args[@]}" "${QWEN_CHROME_START_URL}" >"${LOG_FILE}" 2>&1 </dev/null &
echo $! >"${PID_FILE}"
echo "Qwen Chrome PID: $(cat "${PID_FILE}")"

if ! wait_for_port 127.0.0.1 "${QWEN_CHROME_DEBUG_PORT}"; then
  echo "Qwen Chrome did not open CDP port 127.0.0.1:${QWEN_CHROME_DEBUG_PORT}. See ${LOG_FILE}" >&2
  tail -n 200 "${LOG_FILE}" >&2 || true
  exit 1
fi

if ! wait_for_cdp_ready 127.0.0.1 "${QWEN_CHROME_DEBUG_PORT}" "${QWEN_CHROME_CDP_READY_TRIES}" "${QWEN_CHROME_CDP_READY_DELAY_SECONDS}"; then
  echo "Qwen Chrome CDP endpoint not ready: http://127.0.0.1:${QWEN_CHROME_DEBUG_PORT}/json/version" >&2
  tail -n 200 "${LOG_FILE}" >&2 || true
  exit 1
fi

echo "Qwen Chrome ready."
echo "  cdp=http://127.0.0.1:${QWEN_CHROME_DEBUG_PORT}"
