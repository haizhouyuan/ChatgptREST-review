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
  chatgptrest-finbot-daily-work.service \
  chatgptrest-finbot-daily-work.timer \
  chatgptrest-finbot-theme-batch.service \
  chatgptrest-finbot-theme-batch.timer
do
  install_unit "${SRC_DIR}/${base}" "${UNIT_DST}/${base}"
  echo "Installed ${UNIT_DST}/${base}"
done

systemctl --user daemon-reload
systemctl --user enable --now \
  chatgptrest-finbot-daily-work.timer \
  chatgptrest-finbot-theme-batch.timer
systemctl --user start \
  chatgptrest-finbot-daily-work.service

if command -v /home/yuanhaizhou/.local/bin/openclaw >/dev/null 2>&1; then
  JOB_IDS="$(/home/yuanhaizhou/.local/bin/openclaw cron list --json 2>/dev/null | python3 - <<'PY'
import json, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
jobs = payload.get("jobs") or []
print("\n".join(str(job.get("id") or "").strip() for job in jobs if job.get("id")))
PY
)"
  if grep -qx "finbot-daily-work-morning" <<<"${JOB_IDS}"; then
    /home/yuanhaizhou/.local/bin/openclaw cron disable finbot-daily-work-morning >/dev/null 2>&1 || true
  fi
  if grep -qx "finbot-theme-batch-evening" <<<"${JOB_IDS}"; then
    /home/yuanhaizhou/.local/bin/openclaw cron disable finbot-theme-batch-evening >/dev/null 2>&1 || true
  fi
fi

echo ""
echo "Finbot continuous discovery enabled from checkout: ${ROOT_DIR}"
echo "Timers:"
echo "  systemctl --user status chatgptrest-finbot-daily-work.timer --no-pager"
echo "  systemctl --user status chatgptrest-finbot-theme-batch.timer --no-pager"
echo "Recent runs:"
echo "  journalctl --user -u chatgptrest-finbot-daily-work.service -n 50 --no-pager"
echo "  journalctl --user -u chatgptrest-finbot-theme-batch.service -n 50 --no-pager"
