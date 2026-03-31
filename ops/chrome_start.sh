#!/usr/bin/env bash
# Chrome/CDP bootstrap for the internal driver lane.
# Treat .run/ and the browser profile as live runtime state; repo maintenance must not clean them opportunistically.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${ROOT_DIR}/.run"
RUN_DIR="${ROOT_DIR}/.run/chrome"
mkdir -p "${RUN_DIR}"

DISPLAY="${DISPLAY:-:99}"
CHROME_SCREEN="${CHROME_SCREEN:-1920x1080x24}"
CHROME_USER_DATA_DIR="${CHROME_USER_DATA_DIR:-${ROOT_DIR}/secrets/chrome-profile}"
CHROME_DEBUG_PORT="${CHROME_DEBUG_PORT:-9222}"
CHROME_PROXY_SERVER="${CHROME_PROXY_SERVER:-${ALL_PROXY:-}}"
CHROME_START_URL="${CHROME_START_URL:-https://chatgpt.com/}"
CHROME_WINDOW_SIZE="${CHROME_WINDOW_SIZE:-1280,720}"
CHROME_WINDOW_POSITION="${CHROME_WINDOW_POSITION:-0,0}"
CHROME_NO_SANDBOX="${CHROME_NO_SANDBOX:-1}"
CHROME_DISABLE_DEV_SHM_USAGE="${CHROME_DISABLE_DEV_SHM_USAGE:-1}"
CHROME_DISABLE_GPU="${CHROME_DISABLE_GPU:-1}"
CHROME_DISABLE_SESSION_CRASHED_BUBBLE="${CHROME_DISABLE_SESSION_CRASHED_BUBBLE:-1}"
CHROME_CDP_READY_TRIES="${CHROME_CDP_READY_TRIES:-80}"
CHROME_CDP_READY_DELAY_SECONDS="${CHROME_CDP_READY_DELAY_SECONDS:-0.1}"
# Optional: pass through Chromium host resolver rules (one argument, comma-separated).
# Example: CHROME_HOST_RESOLVER_RULES='MAP gemini.google.com 142.250.0.1'
CHROME_HOST_RESOLVER_RULES="${CHROME_HOST_RESOLVER_RULES:-}"
# Gemini Web often fails with `net::ERR_CONNECTION_CLOSED` when local DNS is polluted for gemini.google.com.
# Best-effort fix: resolve via DoH and map via --host-resolver-rules at Chrome start.
# Disable by setting CHROME_GEMINI_DNS_RESCUE=0.
CHROME_GEMINI_DNS_RESCUE="${CHROME_GEMINI_DNS_RESCUE:-1}"
CHROME_GEMINI_DOH_URL="${CHROME_GEMINI_DOH_URL:-https://dns.google/resolve?name=gemini.google.com&type=A}"
CHROME_GEMINI_DOH_TIMEOUT_SECONDS="${CHROME_GEMINI_DOH_TIMEOUT_SECONDS:-10}"
CHROME_EXTRA_ARGS="${CHROME_EXTRA_ARGS:-}"
if [[ -z "${CHROME_EXTRA_ARGS}" && "${CHROME_DISABLE_GPU}" == "1" ]]; then
  # In this environment, CDP connections can hang when Chrome runs with GPU disabled but without an explicit
  # software GL backend. SwiftShader is Chrome's software renderer; it makes CDP attach much more reliable.
  CHROME_EXTRA_ARGS="--use-gl=swiftshader --enable-unsafe-swiftshader"
fi

PID_FILE="${ROOT_DIR}/.run/chrome.pid"
LOG_FILE="${RUN_DIR}/chrome.log"
XVFB_PID_FILE="${RUN_DIR}/xvfb.pid"
XVFB_LOG_FILE="${RUN_DIR}/xvfb.log"

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

pid_alive() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" 2>/dev/null
}

ensure_x_display() {
  if DISPLAY="${DISPLAY}" xdpyinfo >/dev/null 2>&1; then
    return 0
  fi

  if ! command -v Xvfb >/dev/null 2>&1; then
    echo "Xvfb is required for DISPLAY=${DISPLAY} but is not installed." >&2
    return 1
  fi

  if pid_alive "${XVFB_PID_FILE}"; then
    local stale_pid
    stale_pid="$(cat "${XVFB_PID_FILE}" 2>/dev/null || true)"
    if [[ -n "${stale_pid}" ]]; then
      echo "Tracked worker Xvfb exists but DISPLAY=${DISPLAY} is unavailable; restarting pid=${stale_pid}"
      kill "${stale_pid}" 2>/dev/null || true
      sleep 0.2
    fi
  fi
  rm -f "${XVFB_PID_FILE}"

  echo "Starting worker Xvfb:"
  echo "  DISPLAY=${DISPLAY}"
  echo "  screen=${CHROME_SCREEN}"
  setsid Xvfb "${DISPLAY}" -screen 0 "${CHROME_SCREEN}" -nolisten tcp -ac >"${XVFB_LOG_FILE}" 2>&1 </dev/null &
  echo $! >"${XVFB_PID_FILE}"

  for _ in $(seq 1 50); do
    if DISPLAY="${DISPLAY}" xdpyinfo >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.1
  done

  echo "Worker Xvfb did not become ready for DISPLAY=${DISPLAY}. See ${XVFB_LOG_FILE}" >&2
  tail -n 200 "${XVFB_LOG_FILE}" >&2 || true
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
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null && port_open 127.0.0.1 "${CHROME_DEBUG_PORT}"; then
    echo "Chrome already running (pid=${pid})."
    echo "  cdp=http://127.0.0.1:${CHROME_DEBUG_PORT}"
    exit 0
  fi
fi

if port_open 127.0.0.1 "${CHROME_DEBUG_PORT}"; then
  echo "CDP port already open on 127.0.0.1:${CHROME_DEBUG_PORT} (another Chrome instance may be running)."
  echo "  cdp=http://127.0.0.1:${CHROME_DEBUG_PORT}"
  exit 0
fi

resolve_gemini_doh_ipv4() {
  local doh_url="$1"
  local timeout_seconds="$2"
  command -v curl >/dev/null 2>&1 || return 0

  local json
  json="$(curl -fsS -m "${timeout_seconds}" "${doh_url}" 2>/dev/null || true)"
  [[ -n "${json}" ]] || return 0

  command -v jq >/dev/null 2>&1 || return 0
  local ip
  ip="$(printf '%s' "${json}" | jq -r '.Answer[]? | select(.type==1) | .data' 2>/dev/null | head -n 1 || true)"
  if [[ "${ip}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "${ip}"
  fi
}

mkdir -p "${CHROME_USER_DATA_DIR}"

ensure_x_display

args=(
  --user-data-dir="${CHROME_USER_DATA_DIR}"
  --remote-debugging-address=127.0.0.1
  --remote-debugging-port="${CHROME_DEBUG_PORT}"
  --disable-blink-features=AutomationControlled
  --disable-infobars
  --no-first-run
  --no-default-browser-check
  --password-store=basic
  --window-size="${CHROME_WINDOW_SIZE}"
  --window-position="${CHROME_WINDOW_POSITION}"
)

if [[ "${CHROME_NO_SANDBOX}" == "1" ]]; then
  args+=(--no-sandbox)
fi
if [[ "${CHROME_DISABLE_DEV_SHM_USAGE}" == "1" ]]; then
  args+=(--disable-dev-shm-usage)
fi
if [[ "${CHROME_DISABLE_GPU}" == "1" ]]; then
  args+=(--disable-gpu)
fi
if [[ "${CHROME_DISABLE_SESSION_CRASHED_BUBBLE}" == "1" ]]; then
  args+=(--disable-session-crashed-bubble)
fi
if [[ -n "${CHROME_EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  args+=(${CHROME_EXTRA_ARGS})
fi

host_resolver_rules="${CHROME_HOST_RESOLVER_RULES}"
if [[ -z "${host_resolver_rules}" && "${CHROME_GEMINI_DNS_RESCUE}" == "1" ]]; then
  gemini_ip="$(resolve_gemini_doh_ipv4 "${CHROME_GEMINI_DOH_URL}" "${CHROME_GEMINI_DOH_TIMEOUT_SECONDS}" | head -n 1 | tr -d '\r')"
  if [[ -n "${gemini_ip}" ]]; then
    host_resolver_rules="MAP gemini.google.com ${gemini_ip}"
  fi
fi
if [[ -n "${host_resolver_rules}" ]]; then
  args+=(--host-resolver-rules="${host_resolver_rules}")
fi

if [[ -n "${CHROME_PROXY_SERVER}" ]]; then
  args+=(--proxy-server="${CHROME_PROXY_SERVER}")
fi

export DISPLAY
export HOME="${HOME:-/home/yuanhaizhou}"

echo "Starting Google Chrome:"
echo "  DISPLAY=${DISPLAY}"
echo "  user-data-dir=${CHROME_USER_DATA_DIR}"
echo "  cdp=http://127.0.0.1:${CHROME_DEBUG_PORT}"
if [[ -n "${CHROME_PROXY_SERVER}" ]]; then
  echo "  proxy=${CHROME_PROXY_SERVER}"
fi
if [[ -n "${host_resolver_rules}" ]]; then
  echo "  host_resolver_rules=${host_resolver_rules}"
fi
echo "  no_sandbox=${CHROME_NO_SANDBOX}"
echo "  disable_dev_shm_usage=${CHROME_DISABLE_DEV_SHM_USAGE}"
echo "  disable_gpu=${CHROME_DISABLE_GPU}"
echo "  disable_session_crashed_bubble=${CHROME_DISABLE_SESSION_CRASHED_BUBBLE}"
echo "  log=${LOG_FILE}"

setsid google-chrome "${args[@]}" "${CHROME_START_URL}" >"${LOG_FILE}" 2>&1 </dev/null &
echo $! >"${PID_FILE}"
echo "Chrome PID: $(cat "${PID_FILE}")"

if ! wait_for_port 127.0.0.1 "${CHROME_DEBUG_PORT}"; then
  echo "Chrome did not open CDP port 127.0.0.1:${CHROME_DEBUG_PORT}. See ${LOG_FILE}" >&2
  tail -n 200 "${LOG_FILE}" >&2 || true
  exit 1
fi

if ! wait_for_cdp_ready 127.0.0.1 "${CHROME_DEBUG_PORT}" "${CHROME_CDP_READY_TRIES}" "${CHROME_CDP_READY_DELAY_SECONDS}"; then
  echo "Chrome CDP endpoint not ready: http://127.0.0.1:${CHROME_DEBUG_PORT}/json/version" >&2
  tail -n 200 "${LOG_FILE}" >&2 || true
  exit 1
fi
