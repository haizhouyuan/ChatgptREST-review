#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

mkdir -p logs

ROLE="${1:-${CHATGPTREST_WORKER_ROLE:-all}}"
KIND_PREFIX="${2:-${CHATGPTREST_WORKER_KIND_PREFIX:-}}"

EXTRA_ARGS=()
if [[ -n "${KIND_PREFIX}" ]]; then
  EXTRA_ARGS+=(--kind-prefix "${KIND_PREFIX}")
fi

exec "${REPO_ROOT}/.venv/bin/python" -m chatgptrest.worker.worker --role "${ROLE}" "${EXTRA_ARGS[@]}" 2>&1 | tee -a "${REPO_ROOT}/logs/chatgptrest_worker.log"
