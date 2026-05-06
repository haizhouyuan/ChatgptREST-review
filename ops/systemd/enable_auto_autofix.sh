#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

# `systemctl --user` uses the user's real home directory (from passwd), not always $HOME
# (Codex sessions may override HOME for isolation).
USER_NAME="${USER:-$(id -un)}"
USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"
if [[ -z "${USER_HOME}" ]]; then
  USER_HOME="${HOME}"
fi

ENV_DST_DIR="${USER_HOME}/.config/chatgptrest"
ENV_DST="${ENV_DST_DIR}/chatgptrest.env"

mkdir -p "${ENV_DST_DIR}"
if [[ ! -f "${ENV_DST}" ]]; then
  cp -f "${ROOT_DIR}/ops/systemd/chatgptrest.env.example" "${ENV_DST}"
  echo "Wrote ${ENV_DST}"
fi

python3 - "${ENV_DST}" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
lines = text.splitlines()

def _split_kv(line: str) -> tuple[str, str] | None:
    if not line or line.lstrip().startswith("#"):
        return None
    if "=" not in line:
        return None
    k, v = line.split("=", 1)
    k = k.strip()
    v = v.strip()
    if not k:
        return None
    return k, v

def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1]
    return s

def _merge_no_proxy(existing: str, add: list[str]) -> str:
    cur = [p.strip() for p in _strip_quotes(existing).split(",") if p.strip()]
    cur_l = {p.lower() for p in cur}
    for p in add:
        if p.lower() not in cur_l:
            cur.append(p)
            cur_l.add(p.lower())
    return ",".join(cur) if cur else ",".join(add)

want: dict[str, str] = {
    "CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX": "1",
    "CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MAX_RISK": "medium",
    "CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_MIN_INTERVAL_SECONDS": "300",
    "CHATGPTREST_WORKER_AUTO_CODEX_AUTOFIX_APPLY_ACTIONS": "1",
}

must_no_proxy = ["127.0.0.1", "localhost"]

out: list[str] = []
seen: set[str] = set()
for line in lines:
    kv = _split_kv(line)
    if kv is None:
        out.append(line)
        continue
    k, v = kv
    if k in {"NO_PROXY", "no_proxy"}:
        out.append(f"{k}={_merge_no_proxy(v, must_no_proxy)}")
        seen.add(k)
        continue
    if k in want:
        out.append(f"{k}={want[k]}")
        seen.add(k)
        continue
    out.append(line)

# Ensure NO_PROXY/no_proxy exist.
for k in ("NO_PROXY", "no_proxy"):
    if k not in seen:
        out.append(f"{k}={','.join(must_no_proxy)}")

# Ensure wanted keys exist (append at end).
for k, v in want.items():
    if k not in seen:
        out.append(f"{k}={v}")

path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
print(f"Updated {path}")
PY

cat <<'EOF'

Next:
  systemctl --user restart chatgptrest-worker-send.service chatgptrest-worker-wait.service

To verify:
  journalctl --user -u chatgptrest-worker-wait.service -n 50 --no-pager
EOF
