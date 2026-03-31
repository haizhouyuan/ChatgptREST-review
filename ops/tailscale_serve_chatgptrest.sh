#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

VIEWER_NOVNC_PORT="${VIEWER_NOVNC_PORT:-6082}"
WORKER_VIEWONLY_NOVNC_PORT="${WORKER_VIEWONLY_NOVNC_PORT:-6083}"

TAILSCALE_SERVE_HTTPS_PORT="${TAILSCALE_SERVE_HTTPS_PORT:-443}"
TAILSCALE_SERVE_VIEWER_PATH="${TAILSCALE_SERVE_VIEWER_PATH:-/viewer}"
TAILSCALE_SERVE_WORKER_PATH="${TAILSCALE_SERVE_WORKER_PATH:-/worker}"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale CLI is not installed." >&2
  exit 2
fi

if ! tailscale status >/dev/null 2>&1; then
  echo "tailscale is not running or not authenticated. Run: tailscale up" >&2
  exit 2
fi

TS=(tailscale)
if [[ "$(id -u)" != "0" ]] && command -v sudo >/dev/null 2>&1; then
  TS=(sudo tailscale)
fi

echo "Configuring Tailscale Serve for ChatgptREST noVNC (HTTPS inside tailnet):"
echo "  https:${TAILSCALE_SERVE_HTTPS_PORT}${TAILSCALE_SERVE_VIEWER_PATH} -> http://127.0.0.1:${VIEWER_NOVNC_PORT}"
echo "  https:${TAILSCALE_SERVE_HTTPS_PORT}${TAILSCALE_SERVE_WORKER_PATH} -> http://127.0.0.1:${WORKER_VIEWONLY_NOVNC_PORT}"

set +e
OUT1="$(timeout 5 "${TS[@]}" serve --yes --bg --https="${TAILSCALE_SERVE_HTTPS_PORT}" --set-path="${TAILSCALE_SERVE_VIEWER_PATH}" "http://127.0.0.1:${VIEWER_NOVNC_PORT}" 2>&1)"
RC1=$?
OUT2="$(timeout 5 "${TS[@]}" serve --yes --bg --https="${TAILSCALE_SERVE_HTTPS_PORT}" --set-path="${TAILSCALE_SERVE_WORKER_PATH}" "http://127.0.0.1:${WORKER_VIEWONLY_NOVNC_PORT}" 2>&1)"
RC2=$?
set -e

if [[ "${RC1}" != "0" || "${RC2}" != "0" ]]; then
  echo ""
  echo "tailscale serve failed."
  if [[ -n "${OUT1}" ]]; then
    echo "${OUT1}"
  fi
  if [[ -n "${OUT2}" && "${OUT2}" != "${OUT1}" ]]; then
    echo "${OUT2}"
  fi
  echo ""
  echo "Fallback (no tailscale serve): bind noVNC to the Tailscale IP and use plain HTTP within the tailnet."
  TS_IP="$(tailscale ip -4 | head -n 1 | tr -d '\r')"
  if [[ -z "${TS_IP}" ]]; then
    echo "Cannot determine Tailscale IPv4 address (tailscale ip -4)." >&2
    exit 1
  fi
  echo "Rebinding noVNC listeners to ${TS_IP} ..."
  VIEWER_NOVNC_BIND_HOST="${TS_IP}" bash "${ROOT_DIR}/ops/viewer_start.sh"
  WORKER_VIEWONLY_NOVNC_BIND_HOST="${TS_IP}" bash "${ROOT_DIR}/ops/worker_viewonly_start.sh"
  echo ""
  echo "Tailnet URLs (HTTP):"
  echo "  viewer: http://${TS_IP}:${VIEWER_NOVNC_PORT}/vnc.html"
  echo "  worker (view-only): http://${TS_IP}:${WORKER_VIEWONLY_NOVNC_PORT}/vnc.html"
  echo ""
  echo "If you want HTTPS + /viewer and /worker paths, enable Serve for this tailnet at:"
  echo "  https://login.tailscale.com/f/serve?node=$(tailscale status --json | jq -r '.Self.ID')"
  exit 0
fi

DNS_NAME="$(tailscale status --json | jq -r '.Self.DNSName' | sed 's/\\.$//')"
if [[ -n "${DNS_NAME}" && "${DNS_NAME}" != "null" ]]; then
  echo ""
  echo "Tailnet URLs:"
  echo "  viewer: https://${DNS_NAME}${TAILSCALE_SERVE_VIEWER_PATH}/vnc.html"
  echo "  worker (view-only): https://${DNS_NAME}${TAILSCALE_SERVE_WORKER_PATH}/vnc.html"
fi

echo ""
tailscale serve status
