#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DISPLAY="${DISPLAY:-:99}"
CHROME_DEBUG_PORT="${CHROME_DEBUG_PORT:-9222}"
CHECK_INTERVAL_SECONDS="${CHROME_WATCHDOG_CHECK_INTERVAL_SECONDS:-5}"
RESTART_BACKOFF_SECONDS="${CHROME_WATCHDOG_RESTART_BACKOFF_SECONDS:-3}"
CDP_PROBE_TIMEOUT_SECONDS="${CHROME_WATCHDOG_CDP_PROBE_TIMEOUT_SECONDS:-1.0}"
PORT_FAIL_THRESHOLD="${CHROME_WATCHDOG_PORT_FAIL_THRESHOLD:-2}"
CDP_FAIL_THRESHOLD="${CHROME_WATCHDOG_CDP_FAIL_THRESHOLD:-3}"

# --- NEW: Resilience config ---
MAX_BACKOFF_SECONDS="${CHROME_WATCHDOG_MAX_BACKOFF_SECONDS:-60}"
MAX_RESTARTS_IN_WINDOW="${CHROME_WATCHDOG_MAX_RESTARTS_IN_WINDOW:-5}"
RESTART_WINDOW_SECONDS="${CHROME_WATCHDOG_RESTART_WINDOW_SECONDS:-600}"  # 10 min
CIRCUIT_BREAKER_PAUSE="${CHROME_WATCHDOG_CIRCUIT_BREAKER_PAUSE:-120}"     # 2 min pause
# Issue Ledger lives on the REST API port, not the public MCP port.
API_PORT="${CHATGPTREST_API_PORT:-18711}"
ALERT_ENABLED="${CHROME_WATCHDOG_ALERT_ENABLED:-true}"

PID_FILE="${ROOT_DIR}/.run/chrome.pid"

# --- Restart tracking (circular buffer of epoch timestamps) ---
declare -a restart_timestamps=()
current_backoff="${RESTART_BACKOFF_SECONDS}"

port_open() {
  local host="$1"
  local port="$2"
  python3 - "${host}" "${port}" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(0.3)
try:
  rc = sock.connect_ex((host, port))
  raise SystemExit(0 if rc == 0 else 1)
finally:
  sock.close()
PY
}

cdp_ready() {
  local host="$1"
  local port="$2"
  local timeout="${3:-1.0}"
  python3 - "${host}" "${port}" "${timeout}" <<'PY'
import json
import sys
import urllib.request

host = sys.argv[1]
port = int(sys.argv[2])
timeout = float(sys.argv[3])
url = f"http://{host}:{port}/json/version"
try:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = json.load(resp)
    ws = str((data or {}).get("webSocketDebuggerUrl") or "").strip()
    raise SystemExit(0 if ws else 1)
except Exception:
    raise SystemExit(1)
PY
}

read_pidfile() {
  [[ -f "${PID_FILE}" ]] || return 0
  local pid
  pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    echo "${pid}"
  fi
}

stop_chrome() {
  DISPLAY="${DISPLAY}" CHROME_DEBUG_PORT="${CHROME_DEBUG_PORT}" bash "${ROOT_DIR}/ops/chrome_stop.sh" || true
}

start_chrome() {
  DISPLAY="${DISPLAY}" CHROME_DEBUG_PORT="${CHROME_DEBUG_PORT}" bash "${ROOT_DIR}/ops/chrome_start.sh"
}

# --- NEW: Report alert to Issue Ledger ---
report_alert() {
  local title="$1"
  local symptom="${2:-}"
  if [[ "${ALERT_ENABLED}" != "true" ]]; then
    return 0
  fi
  # Best-effort: don't fail if API is down
  timeout 3 curl -sS -X POST "http://127.0.0.1:${API_PORT}/v1/issues/report" \
    -H "Content-Type: application/json" \
    -d "{
      \"project\": \"ChatgptREST\",
      \"title\": \"[chrome_watchdog] ${title}\",
      \"severity\": \"warning\",
      \"kind\": \"infra\",
      \"source\": \"chrome_watchdog\",
      \"symptom\": \"${symptom}\"
    }" 2>/dev/null || true
}

# --- NEW: Check restart rate (circuit breaker) ---
check_restart_rate() {
  local now
  now="$(date +%s)"
  restart_timestamps+=("${now}")

  # Prune old timestamps outside the window
  local cutoff=$((now - RESTART_WINDOW_SECONDS))
  local new_timestamps=()
  for ts in "${restart_timestamps[@]}"; do
    if (( ts >= cutoff )); then
      new_timestamps+=("${ts}")
    fi
  done
  restart_timestamps=("${new_timestamps[@]}")

  local count=${#restart_timestamps[@]}
  if (( count >= MAX_RESTARTS_IN_WINDOW )); then
    echo "[chrome_watchdog] CIRCUIT BREAKER: ${count} restarts in ${RESTART_WINDOW_SECONDS}s (max=${MAX_RESTARTS_IN_WINDOW})"
    echo "[chrome_watchdog] Pausing for ${CIRCUIT_BREAKER_PAUSE}s to prevent restart storm"
    report_alert "circuit breaker tripped: ${count} restarts in ${RESTART_WINDOW_SECONDS}s" \
                 "Chrome restarted ${count} times within ${RESTART_WINDOW_SECONDS}s. Pausing ${CIRCUIT_BREAKER_PAUSE}s."
    sleep "${CIRCUIT_BREAKER_PAUSE}"
    # Reset after pause
    restart_timestamps=()
    current_backoff="${RESTART_BACKOFF_SECONDS}"
    return 0
  fi
}

# --- NEW: Exponential backoff with cap ---
do_backoff() {
  echo "[chrome_watchdog] backing off ${current_backoff}s (base=${RESTART_BACKOFF_SECONDS}, max=${MAX_BACKOFF_SECONDS})"
  sleep "${current_backoff}"
  # Double backoff, capped at MAX_BACKOFF_SECONDS
  current_backoff=$((current_backoff * 2))
  if (( current_backoff > MAX_BACKOFF_SECONDS )); then
    current_backoff="${MAX_BACKOFF_SECONDS}"
  fi
}

# --- NEW: Reset backoff on successful startup ---
reset_backoff() {
  current_backoff="${RESTART_BACKOFF_SECONDS}"
}

cleanup() {
  echo "[chrome_watchdog] stopping chrome…"
  stop_chrome
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "[chrome_watchdog] starting (DISPLAY=${DISPLAY}, port=${CHROME_DEBUG_PORT})"
echo "[chrome_watchdog] resilience: backoff=${RESTART_BACKOFF_SECONDS}-${MAX_BACKOFF_SECONDS}s, max_restarts=${MAX_RESTARTS_IN_WINDOW}/${RESTART_WINDOW_SECONDS}s, circuit_pause=${CIRCUIT_BREAKER_PAUSE}s"

while true; do
  # Ensure Chrome is running and CDP is responsive.
  if ! start_chrome; then
    echo "[chrome_watchdog] chrome_start failed"
    check_restart_rate
    do_backoff
    continue
  fi

  # Successful start — reset backoff
  reset_backoff

  # Monitor loop: restart if CDP becomes unresponsive or port closes.
  port_fail_count=0
  cdp_fail_count=0
  while true; do
    if ! port_open 127.0.0.1 "${CHROME_DEBUG_PORT}"; then
      port_fail_count=$((port_fail_count + 1))
      echo "[chrome_watchdog] CDP port closed (${port_fail_count}/${PORT_FAIL_THRESHOLD})"
      if (( port_fail_count >= PORT_FAIL_THRESHOLD )); then
        echo "[chrome_watchdog] CDP port closed repeatedly; restarting"
        report_alert "CDP port closed repeatedly" "port ${CHROME_DEBUG_PORT} failed ${port_fail_count} consecutive checks"
        break
      fi
      sleep "${CHECK_INTERVAL_SECONDS}"
      continue
    else
      port_fail_count=0
    fi
    if ! cdp_ready 127.0.0.1 "${CHROME_DEBUG_PORT}" "${CDP_PROBE_TIMEOUT_SECONDS}"; then
      cdp_fail_count=$((cdp_fail_count + 1))
      echo "[chrome_watchdog] CDP probe failed (${cdp_fail_count}/${CDP_FAIL_THRESHOLD})"
      if (( cdp_fail_count >= CDP_FAIL_THRESHOLD )); then
        echo "[chrome_watchdog] CDP probe failed repeatedly; restarting"
        report_alert "CDP probe failed repeatedly" "CDP /json/version failed ${cdp_fail_count} consecutive checks on port ${CHROME_DEBUG_PORT}"
        break
      fi
      sleep "${CHECK_INTERVAL_SECONDS}"
      continue
    else
      cdp_fail_count=0
    fi
    pid="$(read_pidfile || true)"
    if [[ -n "${pid}" ]] && ! kill -0 "${pid}" 2>/dev/null; then
      echo "[chrome_watchdog] chrome pid ${pid} exited; restarting"
      report_alert "Chrome process exited unexpectedly" "PID ${pid} no longer running"
      break
    fi
    sleep "${CHECK_INTERVAL_SECONDS}"
  done

  stop_chrome
  check_restart_rate
  do_backoff
done
