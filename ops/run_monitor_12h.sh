#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

DURATION_SECONDS="${CHATGPTREST_MONITOR_12H_SECONDS:-43200}"
OUT_DIR="${CHATGPTREST_MONITOR_12H_DIR:-${ROOT_DIR}/artifacts/monitor/periodic}"
mkdir -p "${OUT_DIR}"
PY_BIN="${CHATGPTREST_PYTHON_BIN:-${ROOT_DIR}/.venv/bin/python}"
if [[ ! -x "${PY_BIN}" ]]; then
  PY_BIN="python3"
fi

TS="$(date -u +%Y%m%d_%H%M%SZ)"
OUT_JSONL="${OUT_DIR}/monitor_12h_${TS}.jsonl"
OUT_SUMMARY="${OUT_DIR}/monitor_12h_${TS}_summary.md"

"${PY_BIN}" ops/monitor_chatgptrest.py --duration-seconds "${DURATION_SECONDS}" --out "${OUT_JSONL}"
"${PY_BIN}" ops/summarize_monitor_log.py --in "${OUT_JSONL}" --out "${OUT_SUMMARY}"
