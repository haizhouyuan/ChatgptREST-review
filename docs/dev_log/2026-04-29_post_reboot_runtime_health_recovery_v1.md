# 2026-04-29 Post-Reboot Runtime Health Recovery v1

## Context

The operator reported that the host was manually rebooted because resource pressure made the machine unusable. Runtime evidence confirms a boot at `2026-04-29 08:57:01 +0800`.

The previous 12-hour window included:

- an earlyoom kill storm on `2026-04-28 22:20-22:57`, including ChatgptREST dashboard/Chrome and GitNexus-related processes;
- ChatGPT Web send failures before `prompt_sent_at`, including `TargetClosedError`, `Page crashed`, and `BrowserType.launch: Connection closed while reading from the driver`;
- a manual reboot at `2026-04-29 08:57`;
- post-reboot ChatGPT Web driver/wait units skipped by systemd because the manual Pro watch allow file was under `/run/user/1000`, which is intentionally volatile across reboot;
- health probe failures caused by earlyoom log ACL drift on the new-date log;
- `chatgptrest-homepc-tunnel.service` repeatedly restarting every 10 seconds while `192.168.1.17:22` returned `No route to host`;
- OpenMind daily watch failing because a retirement-route test inherited production auth env and saw `401` before it could assert route absence.

## Root Cause

This was not one isolated 429 or Pro job problem. The root cause chain was:

1. Host memory pressure caused earlyoom to kill important runtime processes.
2. Browser/driver instability then surfaced as ChatGPT Web send failures before prompt delivery.
3. The host was manually rebooted to recover from resource pressure.
4. A manual Pro watch systemd gate used an allow file in `/run/user/$UID`; after reboot the file disappeared, so driver/wait stayed blocked even though the durable ChatGPT frontend block had been cleared.
5. Health telemetry degraded because earlyoom log ACLs were date-sensitive.
6. The HomePC reverse tunnel amplified noise by rapidly retrying a known unreachable LAN address.

## Changes

- `ops/manual_pro_watch_guard.py`: default manual Pro watch systemd allow file now lives in persistent repo state: `state/driver/chatgptrest_manual_pro_watch_allow_web_automation`.
- `ops/systemd/*90-manual-pro-watch-hold.conf`: tracked drop-ins now point at the persistent allow file.
- Live user systemd drop-ins were updated to the same persistent allow file and the file was seeded after verifying there were no active/queued jobs.
- `ops/health_probe.py`: earlyoom log reads now fall back to `sudo -n tail -c` when direct reads hit `PermissionError`, so ACL drift does not hide the rest of health status.
- `tests/test_agent_control_plane_retirement.py`: clears production auth tokens so the retired route assertion checks routing, not auth middleware.
- `ops/systemd/chatgptrest-homepc-tunnel.service.d/10-restart-backoff.conf`: tracked slow restart policy for the optional HomePC reverse tunnel.
- Live HomePC tunnel drop-in was installed with `RestartSec=300` / `StartLimitBurst=3`.
- `docs/runbook.md`: updated manual Pro guard, earlyoom health, and tunnel restart guidance.

## Current Runtime Result

After recovery:

- API, public MCP, dashboard, driver, wait worker, ChatGPT send workers, Chrome, and GitNexus HTTP are active.
- `ops/health_probe.py --fix --json` returns `all_ok=true`.
- There are no active `queued/in_progress/cooldown/blocked` jobs at the time of recovery.
- `chatgptrest-homepc-tunnel.service` remains unavailable because `192.168.1.17:22` is unreachable, but it no longer needs to create a tight restart loop.

## Verification

- `py_compile` for `ops/manual_pro_watch_guard.py` and `ops/health_probe.py`
- `pytest -q tests/test_manual_pro_watch_guard.py tests/test_health_probe.py tests/test_agent_control_plane_retirement.py`
- `PYTHONPATH=. ./.venv/bin/python ops/health_probe.py --fix --json`

## Residual Risk

- The manual Pro guard still depends on operators using the release command; stopping the guard service alone intentionally leaves the hold in place.
- HomePC tunnel requires a separate network/Tailscale decision because the direct LAN address is currently unreachable.
- GitNexus CLI impact/context commands reported `No indexed repositories found` in this shell even though `gitnexus status` could see a stale ChatgptREST index; this was treated as a tooling blocker and will need separate GitNexus index repair if impact queries are required.
