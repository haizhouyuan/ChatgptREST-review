#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run/worker_view"
mkdir -p "${RUN_DIR}"

WORKER_DISPLAY="${WORKER_DISPLAY:-:99}"
WORKER_VIEW_VNC_PORT="${WORKER_VIEW_VNC_PORT:-5904}"
WORKER_VIEW_NOVNC_PORT="${WORKER_VIEW_NOVNC_PORT:-6084}"
WORKER_VIEW_NOVNC_BIND_HOST="${WORKER_VIEW_NOVNC_BIND_HOST:-127.0.0.1}"

X11VNC_PID_FILE="${RUN_DIR}/x11vnc.pid"
X11VNC_LOG_FILE="${RUN_DIR}/x11vnc.log"
WEBSOCKIFY_PID_FILE="${RUN_DIR}/websockify.pid"
WEBSOCKIFY_LOG_FILE="${RUN_DIR}/websockify.log"

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

pid_alive() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" 2>/dev/null
}

if ! DISPLAY="${WORKER_DISPLAY}" xdpyinfo >/dev/null 2>&1; then
  echo "Worker display is not available: DISPLAY=${WORKER_DISPLAY}" >&2
  echo "Start the main Chrome/Xvfb first (see ops/chrome_start.sh)." >&2
  exit 2
fi

if port_open 127.0.0.1 "${WORKER_VIEW_VNC_PORT}"; then
  echo "Worker interactive VNC already listening on 127.0.0.1:${WORKER_VIEW_VNC_PORT}"
else
  echo "Starting worker interactive x11vnc:"
  echo "  DISPLAY=${WORKER_DISPLAY}"
  echo "  vnc=127.0.0.1:${WORKER_VIEW_VNC_PORT}"
  setsid x11vnc -display "${WORKER_DISPLAY}" -localhost -rfbport "${WORKER_VIEW_VNC_PORT}" -forever -shared -nopw -noxrecord -noxfixes -noxdamage >"${X11VNC_LOG_FILE}" 2>&1 </dev/null &
  echo $! >"${X11VNC_PID_FILE}"
fi

if port_open "${WORKER_VIEW_NOVNC_BIND_HOST}" "${WORKER_VIEW_NOVNC_PORT}"; then
  echo "Worker interactive noVNC already listening on ${WORKER_VIEW_NOVNC_BIND_HOST}:${WORKER_VIEW_NOVNC_PORT}"
else
  if pid_alive "${WEBSOCKIFY_PID_FILE}"; then
    kill "$(cat "${WEBSOCKIFY_PID_FILE}")" 2>/dev/null || true
    rm -f "${WEBSOCKIFY_PID_FILE}"
    sleep 0.2
  fi
  echo "Starting worker interactive websockify (noVNC):"
  echo "  novnc=http://${WORKER_VIEW_NOVNC_BIND_HOST}:${WORKER_VIEW_NOVNC_PORT}/vnc.html"
  setsid /usr/bin/python3 /usr/bin/websockify --web=/usr/share/novnc --wrap-mode=ignore --log-file="${WEBSOCKIFY_LOG_FILE}" "${WORKER_VIEW_NOVNC_BIND_HOST}:${WORKER_VIEW_NOVNC_PORT}" "127.0.0.1:${WORKER_VIEW_VNC_PORT}" >"${WEBSOCKIFY_LOG_FILE}.stdout" 2>&1 </dev/null &
  echo $! >"${WEBSOCKIFY_PID_FILE}"
fi

echo "Worker interactive ready:"
echo "  noVNC=http://${WORKER_VIEW_NOVNC_BIND_HOST}:${WORKER_VIEW_NOVNC_PORT}/vnc.html"
echo "  DISPLAY=${WORKER_DISPLAY} (interactive)"

