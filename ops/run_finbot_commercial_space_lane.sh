#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "missing python runtime: ${PYTHON_BIN}" >&2
  exit 1
fi

ARTIFACT_PATH="${ROOT_DIR}/artifacts/finbot/theme_runs/$(date +%F)/commercial_space"

cd "${ROOT_DIR}"

"${PYTHON_BIN}" ops/controller_lane_continuity.py sync-manifest \
  --manifest-path config/controller_lanes.json >/dev/null

exec "${PYTHON_BIN}" ops/controller_lane_wrapper.py \
  --lane-id finbot-commercial-space \
  --summary "finbot commercial_space" \
  --artifact-path "${ARTIFACT_PATH}" \
  --executor-kind finbot \
  --provider finagent \
  --model commercial_space_theme_suite \
  -- \
  "${PYTHON_BIN}" ops/openclaw_finbot.py theme-run --theme-slug commercial_space --format json
