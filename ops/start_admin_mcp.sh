#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

mkdir -p logs

export FASTMCP_HOST="${FASTMCP_HOST:-127.0.0.1}"
export FASTMCP_PORT="${FASTMCP_PORT:-18715}"
export CHATGPTREST_MCP_PERSIST_RATE_LIMITS="${CHATGPTREST_MCP_PERSIST_RATE_LIMITS:-1}"
export CHATGPTREST_CLIENT_NAME="${CHATGPTREST_CLIENT_NAME:-chatgptrest-admin-mcp}"
export CHATGPTREST_CLIENT_INSTANCE="${CHATGPTREST_CLIENT_INSTANCE:-$(hostname)-$(id -un)-admin-mcp}"
export CHATGPTREST_REQUEST_ID_PREFIX="${CHATGPTREST_REQUEST_ID_PREFIX:-chatgptrest-admin-mcp}"

exec "${REPO_ROOT}/.venv/bin/python" "${REPO_ROOT}/chatgptrest_admin_mcp_server.py" --transport streamable-http 2>&1 | tee -a "${REPO_ROOT}/logs/chatgptrest_admin_mcp.log"
