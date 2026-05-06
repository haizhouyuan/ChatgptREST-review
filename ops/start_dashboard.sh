#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

mkdir -p logs

HOST="${CHATGPTREST_DASHBOARD_HOST:-127.0.0.1}"
PORT="${CHATGPTREST_DASHBOARD_PORT:-8787}"

exec "${REPO_ROOT}/.venv/bin/python" -m chatgptrest.api.app_dashboard --host "${HOST}" --port "${PORT}" 2>&1 | tee -a "${REPO_ROOT}/logs/chatgptrest_dashboard.log"
