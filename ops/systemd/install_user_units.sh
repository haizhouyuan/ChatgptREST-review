#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="${ROOT_DIR}/ops/systemd"

# `systemctl --user` uses the user's real home directory (from passwd), not always $HOME
# (Codex often overrides HOME for isolation).
USER_NAME="${USER:-$(id -un)}"
USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"
if [[ -z "${USER_HOME}" ]]; then
  USER_HOME="${HOME}"
fi

UNIT_DST="${USER_HOME}/.config/systemd/user"
ENV_DST_DIR="${USER_HOME}/.config/chatgptrest"
ENV_DST="${ENV_DST_DIR}/chatgptrest.env"

mkdir -p "${UNIT_DST}"
mkdir -p "${ENV_DST_DIR}"

if [[ ! -f "${ENV_DST}" ]]; then
  cp -f "${SRC_DIR}/chatgptrest.env.example" "${ENV_DST}"
  echo "Wrote ${ENV_DST}"
else
  echo "Keeping existing ${ENV_DST}"
fi

# Compatibility for shells that override HOME (e.g. Codex isolation profile):
# systemd --user still resolves %h from passwd home, so edits under $HOME/.config
# may not affect running units unless we bridge the paths.
if [[ "${HOME}" != "${USER_HOME}" ]]; then
  ALT_CFG_DIR="${HOME}/.config"
  ALT_ENV_DIR="${ALT_CFG_DIR}/chatgptrest"
  ALT_ENV_FILE="${ALT_ENV_DIR}/chatgptrest.env"
  mkdir -p "${ALT_ENV_DIR}"
  if [[ ! -e "${ALT_ENV_FILE}" ]]; then
    ln -s "${ENV_DST}" "${ALT_ENV_FILE}"
    echo "Linked ${ALT_ENV_FILE} -> ${ENV_DST}"
  else
    echo "Keeping existing ${ALT_ENV_FILE} (not auto-overwritten)"
  fi

  CANON_DROPIN_DIR="${UNIT_DST}/chatgptrest-driver.service.d"
  ALT_DROPIN_DIR="${ALT_CFG_DIR}/systemd/user/chatgptrest-driver.service.d"
  mkdir -p "${CANON_DROPIN_DIR}"
  mkdir -p "$(dirname -- "${ALT_DROPIN_DIR}")"
  if [[ ! -e "${ALT_DROPIN_DIR}" ]]; then
    ln -s "${CANON_DROPIN_DIR}" "${ALT_DROPIN_DIR}"
    echo "Linked ${ALT_DROPIN_DIR} -> ${CANON_DROPIN_DIR}"
  else
    echo "Keeping existing ${ALT_DROPIN_DIR} (not auto-overwritten)"
  fi
fi

install_unit() {
  local src="$1"
  local dst="$2"
  sed "s|__CHATGPTREST_ROOT__|${ROOT_DIR}|g" "${src}" > "${dst}"
}

for f in "${SRC_DIR}"/chatgptrest-*.service "${SRC_DIR}"/chatgptrest-*.target "${SRC_DIR}"/chatgptrest-*.timer; do
  [[ -f "${f}" ]] || continue
  base="$(basename -- "${f}")"
  install_unit "${f}" "${UNIT_DST}/${base}"
  echo "Installed ${UNIT_DST}/${base}"
done

systemctl --user daemon-reload
echo "systemctl --user daemon-reload: ok"

echo ""
echo "Next:"
echo "  systemctl --user enable --now chatgptrest-chrome.service chatgptrest-driver.service chatgptrest-api.service chatgptrest-worker-send.service chatgptrest-worker-wait.service chatgptrest-worker-repair.service chatgptrest-mcp.service"
echo "  # optional internal/admin broad MCP:"
echo "  systemctl --user enable --now chatgptrest-admin-mcp.service"
echo ""
echo "Optional (auto-repair, no prompt send):"
echo "  ops/systemd/enable_auto_autofix.sh"
echo "  systemctl --user restart chatgptrest-worker-send.service chatgptrest-worker-wait.service"
echo ""
echo "Optional (full maint self-heal with guarded runtime autofix):"
echo "  ops/systemd/enable_maint_self_heal.sh"
echo ""
echo "Optional (OpenClaw guardian patrol + notify):"
echo "  systemctl --user enable --now chatgptrest-guardian.timer"
echo ""
echo "Optional (OpenClaw orch agent reconcile doctor):"
echo "  systemctl --user enable --now chatgptrest-orch-doctor.timer"
echo ""
echo "Optional (Issue Ledger -> GitHub sync):"
echo "  systemctl --user enable --now chatgptrest-issue-github-sync.timer"
echo ""
echo "Optional (daily 12h monitor report):"
echo "  systemctl --user enable --now chatgptrest-monitor-12h.timer"
echo ""
echo "Optional (viewer black-screen auto-heal):"
echo "  systemctl --user enable --now chatgptrest-viewer-watchdog.timer"
