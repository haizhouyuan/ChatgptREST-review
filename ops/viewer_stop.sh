#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${VIEWER_RUN_DIR:-${ROOT_DIR}/.run/viewer}"

VIEWER_DISPLAY="${VIEWER_DISPLAY:-:100}"
VIEWER_VNC_PORT="${VIEWER_VNC_PORT:-5902}"
VIEWER_NOVNC_PORT="${VIEWER_NOVNC_PORT:-6082}"
VIEWER_REMOTE_DEBUGGING_PORT="${VIEWER_REMOTE_DEBUGGING_PORT:-}"
VIEWER_USER_DATA_DIR="${VIEWER_USER_DATA_DIR:-${ROOT_DIR}/secrets/chrome-profile-viewer}"

XVFB_PID_FILE="${RUN_DIR}/xvfb.pid"
CHROME_PID_FILE="${RUN_DIR}/chrome.pid"
X11VNC_PID_FILE="${RUN_DIR}/x11vnc.pid"
WEBSOCKIFY_PID_FILE="${RUN_DIR}/websockify.pid"

kill_pid() {
  local pid="$1"
  local label="$2"
  if [[ -z "${pid}" ]]; then
    return 0
  fi
  if ! kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi
  echo "Stopping ${label} (pid=${pid})"
  kill "${pid}" 2>/dev/null || true
  for _ in $(seq 1 50); do
    if ! kill -0 "${pid}" 2>/dev/null; then
      return 0
    fi
    sleep 0.1
  done
  echo "Force-killing ${label} (pid=${pid})"
  kill -9 "${pid}" 2>/dev/null || true
}

kill_pid_file() {
  local pid_file="$1"
  local label="$2"
  [[ -f "${pid_file}" ]] || return 0
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]]; then
    kill_pid "${pid}" "${label}"
  fi
  rm -f "${pid_file}" 2>/dev/null || true
}

kill_listeners() {
  local port="$1"
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi
  local pids
  pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    return 0
  fi
  for pid in ${pids}; do
    kill_pid "${pid}" "listener:${port}"
  done
}

kill_chrome_by_profile() {
  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi
  local pids
  pids="$(pgrep -f "chrome.*--user-data-dir=${VIEWER_USER_DATA_DIR}" 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    return 0
  fi
  for pid in ${pids}; do
    kill_pid "${pid}" "viewer_chrome(profile)"
  done
}

kill_xvfb_by_display() {
  if ! command -v pgrep >/dev/null 2>&1; then
    return 0
  fi
  local display="${VIEWER_DISPLAY}"
  local pids
  pids="$(pgrep -f "Xvfb\\s+${display}(\\s|$)" 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    return 0
  fi
  for pid in ${pids}; do
    kill_pid "${pid}" "viewer_xvfb(${display})"
  done
}

mkdir -p "${RUN_DIR}" 2>/dev/null || true

# Stop network listeners first to avoid long VNC retries.
kill_pid_file "${WEBSOCKIFY_PID_FILE}" "viewer_websockify"
kill_pid_file "${X11VNC_PID_FILE}" "viewer_x11vnc"
kill_listeners "${VIEWER_NOVNC_PORT}"
kill_listeners "${VIEWER_VNC_PORT}"
if [[ -n "${VIEWER_REMOTE_DEBUGGING_PORT}" ]]; then
  kill_listeners "${VIEWER_REMOTE_DEBUGGING_PORT}"
fi

# Stop Chrome next.
kill_pid_file "${CHROME_PID_FILE}" "viewer_chrome"
kill_chrome_by_profile

# Stop Xvfb last.
kill_pid_file "${XVFB_PID_FILE}" "viewer_xvfb"
kill_xvfb_by_display

echo "Viewer stopped."
