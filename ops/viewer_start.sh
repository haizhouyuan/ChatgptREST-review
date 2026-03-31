#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${VIEWER_RUN_DIR:-${ROOT_DIR}/.run/viewer}"
mkdir -p "${RUN_DIR}"

VIEWER_WINDOW_SIZE_RAW="${VIEWER_WINDOW_SIZE-}"
VIEWER_NOVNC_BIND_HOST_RAW="${VIEWER_NOVNC_BIND_HOST-}"

VIEWER_DISPLAY="${VIEWER_DISPLAY:-:100}"
VIEWER_SCREEN="${VIEWER_SCREEN:-1920x1080x24}"
VIEWER_WINDOW_SIZE="${VIEWER_WINDOW_SIZE:-1920,1080}"
VIEWER_WINDOW_POSITION="${VIEWER_WINDOW_POSITION:-0,0}"
VIEWER_USER_DATA_DIR="${VIEWER_USER_DATA_DIR:-${ROOT_DIR}/secrets/chrome-profile-viewer}"
VIEWER_PROXY_SERVER="${VIEWER_PROXY_SERVER:-${ALL_PROXY:-}}"
VIEWER_CLEAR_PROXY_ENV="${VIEWER_CLEAR_PROXY_ENV:-0}"
VIEWER_START_URL="${VIEWER_START_URL:-https://chatgpt.com/}"
VIEWER_DISABLE_GPU="${VIEWER_DISABLE_GPU:-1}"
VIEWER_DISABLE_DEV_SHM_USAGE="${VIEWER_DISABLE_DEV_SHM_USAGE:-1}"
VIEWER_NO_SANDBOX="${VIEWER_NO_SANDBOX:-1}"
VIEWER_CHROME_BIN="${VIEWER_CHROME_BIN:-google-chrome}"
VIEWER_REMOTE_DEBUGGING_ADDRESS="${VIEWER_REMOTE_DEBUGGING_ADDRESS:-127.0.0.1}"
VIEWER_REMOTE_DEBUGGING_PORT="${VIEWER_REMOTE_DEBUGGING_PORT:-}"
VIEWER_DISABLE_AUTOMATION_BLINK="${VIEWER_DISABLE_AUTOMATION_BLINK:-0}"
VIEWER_EXTRA_ARGS="${VIEWER_EXTRA_ARGS:-}"

VIEWER_VNC_PORT="${VIEWER_VNC_PORT:-5902}"
VIEWER_NOVNC_PORT="${VIEWER_NOVNC_PORT:-6082}"
VIEWER_NOVNC_BIND_HOST="${VIEWER_NOVNC_BIND_HOST:-127.0.0.1}"
BIND_HOST_FILE="${RUN_DIR}/novnc_bind_host.txt"

if [[ -z "${VIEWER_NOVNC_BIND_HOST_RAW}" && -f "${BIND_HOST_FILE}" ]]; then
  saved_bind_host="$(cat "${BIND_HOST_FILE}" 2>/dev/null || true)"
  if [[ -n "${saved_bind_host}" ]]; then
    VIEWER_NOVNC_BIND_HOST="${saved_bind_host}"
  fi
fi

if [[ -n "${VIEWER_NOVNC_BIND_HOST_RAW}" ]]; then
  printf '%s\n' "${VIEWER_NOVNC_BIND_HOST}" >"${BIND_HOST_FILE}" 2>/dev/null || true
fi

XVFB_PID_FILE="${RUN_DIR}/xvfb.pid"
XVFB_LOG_FILE="${RUN_DIR}/xvfb.log"
CHROME_PID_FILE="${RUN_DIR}/chrome.pid"
CHROME_LOG_FILE="${RUN_DIR}/chrome.log"
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

x_display_window_size() {
  local display="$1"
  DISPLAY="${display}" xdpyinfo 2>/dev/null | awk '
    /dimensions:/ && !found {
      split($2, a, "x");
      print a[1] "," a[2];
      found = 1;
    }
    END { exit (found ? 0 : 1) }
  '
}

mkdir -p "${VIEWER_USER_DATA_DIR}"

if DISPLAY="${VIEWER_DISPLAY}" xdpyinfo >/dev/null 2>&1; then
  echo "Viewer X display already running: DISPLAY=${VIEWER_DISPLAY}"
else
  if pid_alive "${XVFB_PID_FILE}"; then
    rm -f "${XVFB_PID_FILE}"
  fi
  echo "Starting viewer Xvfb:"
  echo "  DISPLAY=${VIEWER_DISPLAY}"
  echo "  screen=${VIEWER_SCREEN}"
  setsid Xvfb "${VIEWER_DISPLAY}" -screen 0 "${VIEWER_SCREEN}" -nolisten tcp -ac >"${XVFB_LOG_FILE}" 2>&1 </dev/null &
  echo $! >"${XVFB_PID_FILE}"
  for _ in $(seq 1 50); do
    if DISPLAY="${VIEWER_DISPLAY}" xdpyinfo >/dev/null 2>&1; then
      break
    fi
    sleep 0.1
  done
  if ! DISPLAY="${VIEWER_DISPLAY}" xdpyinfo >/dev/null 2>&1; then
    echo "Viewer Xvfb did not become ready. See ${XVFB_LOG_FILE}" >&2
    tail -n 200 "${XVFB_LOG_FILE}" >&2 || true
    exit 1
  fi
fi

if [[ -z "${VIEWER_WINDOW_SIZE_RAW}" ]]; then
  # If the display already existed (e.g. after --chrome-only restarts), keep Chrome window size aligned with the
  # actual Xvfb dimensions to avoid a clipped desktop.
  if actual_size="$(x_display_window_size "${VIEWER_DISPLAY}")"; then
    VIEWER_WINDOW_SIZE="${actual_size}"
  fi
fi

if pid_alive "${CHROME_PID_FILE}"; then
  echo "Viewer Chrome already running (pid=$(cat "${CHROME_PID_FILE}"))."
else
  args=(
    --user-data-dir="${VIEWER_USER_DATA_DIR}"
    --disable-infobars
    --no-first-run
    --no-default-browser-check
    --password-store=basic
    --window-size="${VIEWER_WINDOW_SIZE}"
    --window-position="${VIEWER_WINDOW_POSITION}"
  )
  if [[ -n "${VIEWER_REMOTE_DEBUGGING_PORT}" ]]; then
    args+=(--remote-debugging-address="${VIEWER_REMOTE_DEBUGGING_ADDRESS}")
    args+=(--remote-debugging-port="${VIEWER_REMOTE_DEBUGGING_PORT}")
  fi
  if [[ "${VIEWER_DISABLE_AUTOMATION_BLINK}" == "1" ]]; then
    args+=(--disable-blink-features=AutomationControlled)
  fi
  if [[ "${VIEWER_NO_SANDBOX}" == "1" ]]; then
    args+=(--no-sandbox)
  fi
  if [[ "${VIEWER_DISABLE_DEV_SHM_USAGE}" == "1" ]]; then
    args+=(--disable-dev-shm-usage)
  fi
  if [[ "${VIEWER_DISABLE_GPU}" == "1" ]]; then
    args+=(--disable-gpu)
    if [[ -z "${VIEWER_EXTRA_ARGS}" ]]; then
      VIEWER_EXTRA_ARGS="--use-gl=swiftshader --enable-unsafe-swiftshader"
    fi
  fi
  if [[ -n "${VIEWER_EXTRA_ARGS}" ]]; then
    # shellcheck disable=SC2206
    args+=(${VIEWER_EXTRA_ARGS})
  fi
  if [[ -n "${VIEWER_PROXY_SERVER}" ]]; then
    args+=(--proxy-server="${VIEWER_PROXY_SERVER}")
  elif [[ "${VIEWER_CLEAR_PROXY_ENV}" == "1" ]]; then
    args+=(--no-proxy-server)
  fi

  echo "Starting viewer Chrome:"
  echo "  chrome-bin=${VIEWER_CHROME_BIN}"
  echo "  DISPLAY=${VIEWER_DISPLAY}"
  echo "  user-data-dir=${VIEWER_USER_DATA_DIR}"
  if [[ -n "${VIEWER_REMOTE_DEBUGGING_PORT}" ]]; then
    echo "  cdp=http://${VIEWER_REMOTE_DEBUGGING_ADDRESS}:${VIEWER_REMOTE_DEBUGGING_PORT}"
  fi
  if [[ -n "${VIEWER_PROXY_SERVER}" ]]; then
    echo "  proxy=${VIEWER_PROXY_SERVER}"
  fi
  echo "  url=${VIEWER_START_URL}"
  echo "  log=${CHROME_LOG_FILE}"
  DISPLAY="${VIEWER_DISPLAY}" setsid "${VIEWER_CHROME_BIN}" "${args[@]}" "${VIEWER_START_URL}" >"${CHROME_LOG_FILE}" 2>&1 </dev/null &
  echo $! >"${CHROME_PID_FILE}"
  echo "Viewer Chrome PID: $(cat "${CHROME_PID_FILE}")"
fi

if port_open 127.0.0.1 "${VIEWER_VNC_PORT}"; then
  echo "Viewer VNC already listening on 127.0.0.1:${VIEWER_VNC_PORT}"
else
  echo "Starting viewer x11vnc:"
  echo "  DISPLAY=${VIEWER_DISPLAY}"
  echo "  vnc=127.0.0.1:${VIEWER_VNC_PORT}"
  setsid x11vnc -display "${VIEWER_DISPLAY}" -localhost -rfbport "${VIEWER_VNC_PORT}" -forever -shared -nopw -noxrecord -noxfixes -noxdamage >"${X11VNC_LOG_FILE}" 2>&1 </dev/null &
  echo $! >"${X11VNC_PID_FILE}"
fi

if port_open "${VIEWER_NOVNC_BIND_HOST}" "${VIEWER_NOVNC_PORT}"; then
  echo "Viewer noVNC already listening on ${VIEWER_NOVNC_BIND_HOST}:${VIEWER_NOVNC_PORT}"
else
  if pid_alive "${WEBSOCKIFY_PID_FILE}"; then
    kill "$(cat "${WEBSOCKIFY_PID_FILE}")" 2>/dev/null || true
    rm -f "${WEBSOCKIFY_PID_FILE}"
    sleep 0.2
  fi
  echo "Starting viewer websockify (noVNC):"
  echo "  novnc=http://${VIEWER_NOVNC_BIND_HOST}:${VIEWER_NOVNC_PORT}/vnc.html"
  setsid /usr/bin/python3 /usr/bin/websockify --web=/usr/share/novnc --wrap-mode=ignore --log-file="${WEBSOCKIFY_LOG_FILE}" "${VIEWER_NOVNC_BIND_HOST}:${VIEWER_NOVNC_PORT}" "127.0.0.1:${VIEWER_VNC_PORT}" >"${WEBSOCKIFY_LOG_FILE}.stdout" 2>&1 </dev/null &
  echo $! >"${WEBSOCKIFY_PID_FILE}"
fi

echo "Viewer ready:"
echo "  noVNC=http://${VIEWER_NOVNC_BIND_HOST}:${VIEWER_NOVNC_PORT}/vnc.html"
echo "  DISPLAY=${VIEWER_DISPLAY}"
