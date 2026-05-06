#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

SOAK_SECONDS="${CHATGPTREST_SOAK_SECONDS:-3600}"
OUT_DIR="${CHATGPTREST_SOAK_DIR:-${REPO_ROOT}/artifacts/monitor/soak}"
mkdir -p "${OUT_DIR}"

TS="$(date -u +%Y%m%d_%H%M%SZ)"
OUT="${OUT_DIR}/soak_${SOAK_SECONDS}s_${TS}.jsonl"
SUMMARY="${OUT%.jsonl}_summary.md"

echo "[soak] start"
echo "${OUT}"

python3 ops/monitor_chatgptrest.py --duration-seconds "${SOAK_SECONDS}" --out "${OUT}"

echo "[soak] done, writing summary"
python3 ops/summarize_monitor_log.py --in "${OUT}" --out "${SUMMARY}"

echo "[soak] summary ready ${SUMMARY}"

exec bash
