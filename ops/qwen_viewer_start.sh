#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${QWEN_VIEWER_RUN_DIR:-${ROOT_DIR}/.run/qwen_viewer}"
mkdir -p "${RUN_DIR}"

QWEN_VIEWER_DISPLAY="${QWEN_VIEWER_DISPLAY:-:101}"
QWEN_VIEWER_SCREEN="${QWEN_VIEWER_SCREEN:-1920x1080x24}"
QWEN_VIEWER_VNC_PORT="${QWEN_VIEWER_VNC_PORT:-5905}"
QWEN_VIEWER_NOVNC_PORT="${QWEN_VIEWER_NOVNC_PORT:-6085}"
QWEN_VIEWER_NOVNC_BIND_HOST_RAW="${QWEN_VIEWER_NOVNC_BIND_HOST-}"
QWEN_VIEWER_NOVNC_BIND_HOST="${QWEN_VIEWER_NOVNC_BIND_HOST:-127.0.0.1}"
BIND_HOST_FILE="${RUN_DIR}/novnc_bind_host.txt"

if [[ -z "${QWEN_VIEWER_NOVNC_BIND_HOST_RAW}" && -f "${BIND_HOST_FILE}" ]]; then
  saved_bind_host="$(cat "${BIND_HOST_FILE}" 2>/dev/null || true)"
  if [[ -n "${saved_bind_host}" ]]; then
    QWEN_VIEWER_NOVNC_BIND_HOST="${saved_bind_host}"
  fi
fi

if [[ -n "${QWEN_VIEWER_NOVNC_BIND_HOST_RAW}" ]]; then
  printf '%s\n' "${QWEN_VIEWER_NOVNC_BIND_HOST}" >"${BIND_HOST_FILE}" 2>/dev/null || true
fi

XVFB_PID_FILE="${RUN_DIR}/xvfb.pid"
XVFB_LOG_FILE="${RUN_DIR}/xvfb.log"
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

rm_stale_pidfile() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 0
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
    rm -f "${pid_file}" 2>/dev/null || true
  fi
}

if DISPLAY="${QWEN_VIEWER_DISPLAY}" xdpyinfo >/dev/null 2>&1; then
  echo "Qwen viewer X display already running: DISPLAY=${QWEN_VIEWER_DISPLAY}"
else
  rm_stale_pidfile "${XVFB_PID_FILE}"
  echo "Starting Qwen viewer Xvfb:"
  echo "  DISPLAY=${QWEN_VIEWER_DISPLAY}"
  echo "  screen=${QWEN_VIEWER_SCREEN}"
  setsid Xvfb "${QWEN_VIEWER_DISPLAY}" -screen 0 "${QWEN_VIEWER_SCREEN}" -nolisten tcp -ac >"${XVFB_LOG_FILE}" 2>&1 </dev/null &
  echo $! >"${XVFB_PID_FILE}"
  for _ in $(seq 1 50); do
    if DISPLAY="${QWEN_VIEWER_DISPLAY}" xdpyinfo >/dev/null 2>&1; then
      break
    fi
    sleep 0.1
  done
  if ! DISPLAY="${QWEN_VIEWER_DISPLAY}" xdpyinfo >/dev/null 2>&1; then
    echo "Qwen viewer Xvfb did not become ready. See ${XVFB_LOG_FILE}" >&2
    tail -n 200 "${XVFB_LOG_FILE}" >&2 || true
    exit 1
  fi
fi

if port_open 127.0.0.1 "${QWEN_VIEWER_VNC_PORT}"; then
  echo "Qwen viewer VNC already listening on 127.0.0.1:${QWEN_VIEWER_VNC_PORT}"
else
  rm_stale_pidfile "${X11VNC_PID_FILE}"
  echo "Starting Qwen viewer x11vnc:"
  echo "  DISPLAY=${QWEN_VIEWER_DISPLAY}"
  echo "  vnc=127.0.0.1:${QWEN_VIEWER_VNC_PORT}"
  setsid x11vnc -display "${QWEN_VIEWER_DISPLAY}" -localhost -rfbport "${QWEN_VIEWER_VNC_PORT}" -forever -shared -nopw -noxrecord -noxfixes -noxdamage >"${X11VNC_LOG_FILE}" 2>&1 </dev/null &
  echo $! >"${X11VNC_PID_FILE}"
fi

if port_open "${QWEN_VIEWER_NOVNC_BIND_HOST}" "${QWEN_VIEWER_NOVNC_PORT}"; then
  echo "Qwen viewer noVNC already listening on ${QWEN_VIEWER_NOVNC_BIND_HOST}:${QWEN_VIEWER_NOVNC_PORT}"
else
  if pid_alive "${WEBSOCKIFY_PID_FILE}"; then
    kill "$(cat "${WEBSOCKIFY_PID_FILE}")" 2>/dev/null || true
    rm -f "${WEBSOCKIFY_PID_FILE}" 2>/dev/null || true
    sleep 0.2
  fi
  echo "Starting Qwen viewer websockify (noVNC):"
  echo "  novnc=http://${QWEN_VIEWER_NOVNC_BIND_HOST}:${QWEN_VIEWER_NOVNC_PORT}/vnc.html"
  setsid /usr/bin/python3 /usr/bin/websockify --web=/usr/share/novnc --wrap-mode=ignore --log-file="${WEBSOCKIFY_LOG_FILE}" "${QWEN_VIEWER_NOVNC_BIND_HOST}:${QWEN_VIEWER_NOVNC_PORT}" "127.0.0.1:${QWEN_VIEWER_VNC_PORT}" >"${WEBSOCKIFY_LOG_FILE}.stdout" 2>&1 </dev/null &
  echo $! >"${WEBSOCKIFY_PID_FILE}"
fi

echo "Ensuring Qwen Chrome is running on ${QWEN_VIEWER_DISPLAY} (CDP :9335, no proxy)…"
DISPLAY="${QWEN_VIEWER_DISPLAY}" "${ROOT_DIR}/ops/qwen_chrome_start.sh"

echo "Qwen viewer ready:"
echo "  noVNC=http://${QWEN_VIEWER_NOVNC_BIND_HOST}:${QWEN_VIEWER_NOVNC_PORT}/vnc.html"
echo "  DISPLAY=${QWEN_VIEWER_DISPLAY}"
echo "  cdp=http://127.0.0.1:9335"
