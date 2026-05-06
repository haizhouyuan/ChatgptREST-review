#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DISPLAY="${DISPLAY:-:99}"
QWEN_CHROME_USER_DATA_DIR="${QWEN_CHROME_USER_DATA_DIR:-${ROOT_DIR}/secrets/qwen-chrome-profile}"
QWEN_CHROME_DEBUG_PORT="${QWEN_CHROME_DEBUG_PORT:-9335}"
QWEN_CHROME_STOP_TIMEOUT_SECONDS="${QWEN_CHROME_STOP_TIMEOUT_SECONDS:-8}"
QWEN_CHROME_KILL_TIMEOUT_SECONDS="${QWEN_CHROME_KILL_TIMEOUT_SECONDS:-4}"

PID_FILE="${ROOT_DIR}/.run/qwen_chrome.pid"

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

wait_for_port_close() {
  local host="$1"
  local port="$2"
  local timeout_seconds="${3:-8}"
  local deadline
  deadline="$(python3 - "${timeout_seconds}" <<'PY'
import sys, time
timeout=float(sys.argv[1])
print(time.time()+timeout)
PY
)"

  while true; do
    if ! port_open "${host}" "${port}"; then
      return 0
    fi
    now="$(python3 - <<'PY'
import time
print(time.time())
PY
)"
    if python3 - "${now}" "${deadline}" <<'PY'
import sys
now=float(sys.argv[1])
deadline=float(sys.argv[2])
raise SystemExit(0 if now >= deadline else 1)
PY
    then
      return 1
    fi
    sleep 0.2
  done
}

read_pidfile() {
  [[ -f "${PID_FILE}" ]] || return 0
  local pid
  pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    echo "${pid}"
  fi
}

listener_pid_from_ss() {
  local port="$1"
  command -v ss >/dev/null 2>&1 || return 0
  ss -lntp 2>/dev/null \
    | grep -E ":${port}\\b" \
    | sed -n 's/.*pid=\\([0-9][0-9]*\\).*/\\1/p' \
    | head -n 1 \
    || true
}

pgrep_debug_port() {
  local port="$1"
  local user_data_dir="$2"
  command -v pgrep >/dev/null 2>&1 || return 0
  pgrep -f -- "--remote-debugging-port=${port} .*--user-data-dir=${user_data_dir}" || true
}

unique_pids() {
  awk 'NF{print $0}' | sort -n | uniq
}

pids="$((
  read_pidfile || true
  listener_pid_from_ss "${QWEN_CHROME_DEBUG_PORT}" || true
  pgrep_debug_port "${QWEN_CHROME_DEBUG_PORT}" "${QWEN_CHROME_USER_DATA_DIR}" || true
) | unique_pids)"

if [[ -z "${pids}" ]]; then
  if port_open 127.0.0.1 "${QWEN_CHROME_DEBUG_PORT}"; then
    echo "Qwen Chrome CDP port is open (127.0.0.1:${QWEN_CHROME_DEBUG_PORT}) but no tracked PID found."
    echo "Refusing to kill unknown listener; inspect manually."
    exit 2
  fi
  echo "Qwen Chrome not running."
  exit 0
fi

echo "Stopping Qwen Chrome (DISPLAY=${DISPLAY}, cdp=http://127.0.0.1:${QWEN_CHROME_DEBUG_PORT})"
echo "  pids: ${pids}"

for pid in ${pids}; do
  if kill -0 "${pid}" 2>/dev/null; then
    if kill -TERM -- "-${pid}" 2>/dev/null; then
      continue
    fi
    kill -TERM "${pid}" 2>/dev/null || true
  fi
done

if ! wait_for_port_close 127.0.0.1 "${QWEN_CHROME_DEBUG_PORT}" "${QWEN_CHROME_STOP_TIMEOUT_SECONDS}"; then
  echo "Qwen Chrome still listening on 127.0.0.1:${QWEN_CHROME_DEBUG_PORT}; sending SIGKILL…"
  for pid in ${pids}; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill -KILL -- "-${pid}" 2>/dev/null || kill -KILL "${pid}" 2>/dev/null || true
    fi
  done
  wait_for_port_close 127.0.0.1 "${QWEN_CHROME_DEBUG_PORT}" "${QWEN_CHROME_KILL_TIMEOUT_SECONDS}" || true
fi

rm -f "${PID_FILE}" || true
echo "Qwen Chrome stopped."
