#!/usr/bin/env bash
# Primary runtime API entry.
# Starts the FastAPI app on the public REST port; it does not launch worker, driver, or MCP sidecars.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

mkdir -p logs

HOST="${CHATGPTREST_HOST:-127.0.0.1}"
PORT="${CHATGPTREST_PORT:-18711}"

exec "${REPO_ROOT}/.venv/bin/python" -m chatgptrest.api.app --host "${HOST}" --port "${PORT}" 2>&1 | tee -a "${REPO_ROOT}/logs/chatgptrest_api.log"
