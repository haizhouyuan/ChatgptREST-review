#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="${ROOT_DIR}/ops/systemd"
USER_NAME="${USER:-$(id -un)}"
USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"
if [[ -z "${USER_HOME}" ]]; then
  USER_HOME="${HOME}"
fi
UNIT_DST="${USER_HOME}/.config/systemd/user"
mkdir -p "${UNIT_DST}"

install_unit() {
  local src="$1"
  local dst="$2"
  sed "s|__CHATGPTREST_ROOT__|${ROOT_DIR}|g" "${src}" > "${dst}"
}

for base in \
  chatgptrest-finbot-commercial-space.service \
  chatgptrest-finbot-commercial-space.timer
do
  install_unit "${SRC_DIR}/${base}" "${UNIT_DST}/${base}"
  echo "Installed ${UNIT_DST}/${base}"
done

systemctl --user daemon-reload
systemctl --user enable --now chatgptrest-finbot-commercial-space.timer
systemctl --user start chatgptrest-finbot-commercial-space.service

echo ""
echo "Commercial space finbot lane enabled from checkout: ${ROOT_DIR}"
echo "Status:"
echo "  systemctl --user status chatgptrest-finbot-commercial-space.timer --no-pager"
echo "  systemctl --user status chatgptrest-finbot-commercial-space.service --no-pager"
echo "Logs:"
echo "  journalctl --user -u chatgptrest-finbot-commercial-space.service -n 50 --no-pager"
