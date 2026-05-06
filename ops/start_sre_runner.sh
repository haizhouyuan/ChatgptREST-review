#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

export CHATGPTREST_SRE_ENABLE_GITNEXUS="${CHATGPTREST_SRE_ENABLE_GITNEXUS:-1}"
export CHATGPTREST_SRE_GITNEXUS_QUERY_CMD="${CHATGPTREST_SRE_GITNEXUS_QUERY_CMD:-/usr/bin/env npm_config_cache=/tmp/chatgptrest-gitnexus-npx-cache npx --yes gitnexus query}"
export CHATGPTREST_SRE_GITNEXUS_TIMEOUT_SECONDS="${CHATGPTREST_SRE_GITNEXUS_TIMEOUT_SECONDS:-20}"

exec "${REPO_ROOT}/ops/start_worker.sh" all sre.
