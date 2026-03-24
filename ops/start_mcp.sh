#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

mkdir -p logs

load_env_file() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${path}"
    set +a
  fi
}

load_env_file "${HOME}/.config/chatgptrest/chatgptrest.env"
load_env_file "/vol1/maint/MAIN/secrets/credentials.env"

export FASTMCP_HOST="${FASTMCP_HOST:-127.0.0.1}"
export FASTMCP_PORT="${FASTMCP_PORT:-18712}"
export CHATGPTREST_AGENT_MCP_PORT="${CHATGPTREST_AGENT_MCP_PORT:-${FASTMCP_PORT}}"
export CHATGPTREST_CLIENT_NAME="${CHATGPTREST_CLIENT_NAME:-chatgptrest-agent-mcp}"
export CHATGPTREST_CLIENT_INSTANCE="${CHATGPTREST_CLIENT_INSTANCE:-$(hostname)-$(id -un)-agent-mcp}"
export CHATGPTREST_REQUEST_ID_PREFIX="${CHATGPTREST_REQUEST_ID_PREFIX:-chatgptrest-agent-mcp}"

exec "${REPO_ROOT}/.venv/bin/python" "${REPO_ROOT}/chatgptrest_agent_mcp_server.py" --transport streamable-http 2>&1 | tee -a "${REPO_ROOT}/logs/chatgptrest_agent_mcp.log"
