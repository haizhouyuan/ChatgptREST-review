#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

# Default: every 5 minutes.
INTERVAL_SECONDS="${MIHOMO_DELAY_INTERVAL_SECONDS:-300}"

while true; do
  "${REPO_ROOT}/.venv/bin/python" "${REPO_ROOT}/ops/mihomo_delay_snapshot.py" || true
  sleep "${INTERVAL_SECONDS}"
done

