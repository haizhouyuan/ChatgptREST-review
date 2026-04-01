#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run/viewer"

MODE="${1:---full}"

VIEWER_NOVNC_PORT="${VIEWER_NOVNC_PORT:-6082}"
WEBSOCKIFY_PID_FILE="${RUN_DIR}/websockify.pid"
CHROME_PID_FILE="${RUN_DIR}/chrome.pid"
CHROME_LOG_FILE="${RUN_DIR}/chrome.log"

pid_alive() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" 2>/dev/null
}

detect_bind_host() {
  if [[ -n "${VIEWER_NOVNC_BIND_HOST:-}" ]]; then
    echo "${VIEWER_NOVNC_BIND_HOST}"
    return 0
  fi
  if ! pid_alive "${WEBSOCKIFY_PID_FILE}"; then
    echo ""
    return 0
  fi
  local pid args
  pid="$(cat "${WEBSOCKIFY_PID_FILE}" 2>/dev/null || true)"
  args="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
  if [[ -z "${args}" ]]; then
    echo ""
    return 0
  fi
  python3 - "${args}" "${VIEWER_NOVNC_PORT}" <<'PY'
import shlex
import sys

args = sys.argv[1]
port = str(sys.argv[2])
try:
    toks = shlex.split(args)
except Exception:
    toks = args.split()

for tok in toks:
    if tok.endswith(":" + port):
        host = tok[: -(len(port) + 1)]
        if host:
            print(host)
            raise SystemExit(0)
print("")
PY
}

restart_full() {
  local bind_host
  bind_host="$(detect_bind_host)"
  if [[ -n "${bind_host}" ]]; then
    export VIEWER_NOVNC_BIND_HOST="${bind_host}"
  fi
  bash "${ROOT_DIR}/ops/viewer_stop.sh"
  bash "${ROOT_DIR}/ops/viewer_start.sh"
}

restart_chrome_only() {
  local bind_host
  bind_host="$(detect_bind_host)"
  if [[ -n "${bind_host}" ]]; then
    export VIEWER_NOVNC_BIND_HOST="${bind_host}"
  fi
  if pid_alive "${CHROME_PID_FILE}"; then
    pid="$(cat "${CHROME_PID_FILE}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]]; then
      echo "Stopping viewer Chrome (pid=${pid})"
      kill "${pid}" 2>/dev/null || true
      sleep 0.5
      kill -9 "${pid}" 2>/dev/null || true
    fi
    rm -f "${CHROME_PID_FILE}" 2>/dev/null || true
  fi
  bash "${ROOT_DIR}/ops/viewer_start.sh"
}

case "${MODE}" in
  --full|"")
    restart_full
    ;;
  --chrome-only)
    restart_chrome_only
    ;;
  *)
    echo "Usage: $0 [--full|--chrome-only]" >&2
    exit 2
    ;;
esac

echo "Viewer restart done. If Chrome still shows a blank page, check: ${CHROME_LOG_FILE}"
