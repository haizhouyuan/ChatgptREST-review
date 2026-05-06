#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
COMMON_GIT_DIR="$(git -C "${ROOT_DIR}" rev-parse --path-format=absolute --git-common-dir)"
STATE_ROOT="$(cd -- "${COMMON_GIT_DIR}/.." && pwd)"

ENABLE_WORKER_AUTO_CODEX_AUTOFIX=0
ENABLE_CODEX_SRE_AUTOFIX=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-worker-auto-autofix)
      ENABLE_WORKER_AUTO_CODEX_AUTOFIX=1
      shift
      ;;
    --with-codex-sre-autofix)
      ENABLE_CODEX_SRE_AUTOFIX=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--with-worker-auto-autofix] [--with-codex-sre-autofix]" >&2
      exit 2
      ;;
  esac
done

if [[ "${ENABLE_WORKER_AUTO_CODEX_AUTOFIX}" == "1" ]]; then
  "${ROOT_DIR}/ops/systemd/enable_auto_autofix.sh"
fi

USER_NAME="${USER:-$(id -un)}"
USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"
if [[ -z "${USER_HOME}" ]]; then
  USER_HOME="${HOME}"
fi

DROPIN_DIR="${USER_HOME}/.config/systemd/user/chatgptrest-maint-daemon.service.d"
DROPIN_PATH="${DROPIN_DIR}/30-self-heal.conf"
RUNTIME_UNITS=(
  "chatgptrest-api.service"
  "chatgptrest-maint-daemon.service"
  "chatgptrest-mcp.service"
  "chatgptrest-worker-send.service"
  "chatgptrest-worker-wait.service"
  "chatgptrest-worker-repair.service"
  "chatgptrest-worker-send-chatgpt@.service"
  "chatgptrest-worker-send-gemini@.service"
  "chatgptrest-worker-send-qwen.service"
)

write_runtime_dropin() {
  local unit_name="$1"
  local unit_dir="${USER_HOME}/.config/systemd/user/${unit_name}.d"
  local unit_path="${unit_dir}/20-runtime-worktree.conf"
  local stale_override="${unit_dir}/99-current-working-tree.conf"
  local disabled_override="${unit_dir}/99-current-working-tree.conf.disabled-by-maint-self-heal"
  mkdir -p "${unit_dir}"
  if [[ -f "${stale_override}" ]]; then
    mv -f "${stale_override}" "${disabled_override}"
  fi
  cat > "${unit_path}" <<EOF
[Service]
WorkingDirectory=${ROOT_DIR}
Environment=PYTHONPATH=${ROOT_DIR}
Environment=CHATGPTREST_DB_PATH=${STATE_ROOT}/state/jobdb.sqlite3
Environment=CHATGPTREST_ARTIFACTS_DIR=${STATE_ROOT}/artifacts
EOF
  if [[ "${unit_name}" == "chatgptrest-mcp.service" ]]; then
    cat >> "${unit_path}" <<EOF
ExecStart=
ExecStart=/vol1/1000/projects/ChatgptREST/.venv/bin/python ${ROOT_DIR}/chatgptrest_agent_mcp_server.py --transport streamable-http
EOF
  fi
}

for unit_name in "${RUNTIME_UNITS[@]}"; do
  write_runtime_dropin "${unit_name}"
done

mkdir -p "${DROPIN_DIR}"
MAINT_DAEMON_CMD="/vol1/1000/projects/ChatgptREST/.venv/bin/python ops/maint_daemon.py --enable-auto-pause --auto-pause-mode send --enable-chatgptmcp-evidence --enable-chatgptmcp-capture-ui --enable-auto-repair-check --enable-codex-sre-analyze --enable-ui-canary"
if [[ "${ENABLE_CODEX_SRE_AUTOFIX}" == "1" ]]; then
  MAINT_DAEMON_CMD+=" --enable-codex-sre-autofix --codex-sre-autofix-allow-actions capture_ui,clear_blocked,restart_driver,restart_chrome,switch_gemini_proxy --codex-sre-autofix-max-risk medium"
fi
cat > "${DROPIN_PATH}" <<EOF
[Service]
WorkingDirectory=${ROOT_DIR}
Environment=PYTHONPATH=${ROOT_DIR}
ExecStart=
ExecStart=${MAINT_DAEMON_CMD}
EOF

systemctl --user daemon-reload
systemctl --user restart \
  chatgptrest-api.service \
  chatgptrest-mcp.service \
  chatgptrest-maint-daemon.service \
  chatgptrest-worker-send.service \
  chatgptrest-worker-wait.service \
  chatgptrest-worker-repair.service

cat <<EOF
Enabled maint self-heal:
  code checkout: ${ROOT_DIR}
  shared state root: ${STATE_ROOT}
  runtime drop-ins:
    ${USER_HOME}/.config/systemd/user/chatgptrest-api.service.d/20-runtime-worktree.conf
    ${USER_HOME}/.config/systemd/user/chatgptrest-mcp.service.d/20-runtime-worktree.conf
    ${USER_HOME}/.config/systemd/user/chatgptrest-worker-*.service.d/20-runtime-worktree.conf
  drop-in: ${DROPIN_PATH}
  worker auto Codex autofix: ${ENABLE_WORKER_AUTO_CODEX_AUTOFIX}
  maint daemon Codex SRE autofix: ${ENABLE_CODEX_SRE_AUTOFIX}

Verification:
  systemctl --user status chatgptrest-maint-daemon.service --no-pager
  systemctl --user show chatgptrest-api.service -p FragmentPath -p DropInPaths --value
  systemctl --user show chatgptrest-mcp.service -p FragmentPath -p DropInPaths --value
  systemctl --user show chatgptrest-worker-send.service -p Environment --value
EOF
