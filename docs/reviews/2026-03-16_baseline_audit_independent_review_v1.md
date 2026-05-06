# 2026-03-16 Baseline Audit Independent Review v1

## Scope

This document records an independent review of the baseline audit claims raised on 2026-03-16 for the ChatgptREST production host.

The reviewed claims were:

1. Advisor API on port `18713` is not running, and this is a `P0`
2. `chatgptrest-health-probe.service` is failed because `ops/health_probe.py` was deleted
3. `chatgptrest-ui-canary.service` is failed because `ops/ui_canary_sidecar.py` was deleted
4. `chatgptrest-monitor-12h.service` is failed and only needs `systemctl --user reset-failed`

## Verdict

### Confirmed

- `chatgptrest-health-probe.service` is currently broken because its `ExecStart` points to a file that does not exist:
  - `/home/yuanhaizhou/.config/systemd/user/chatgptrest-health-probe.service`
  - `ExecStart=/vol1/1000/projects/ChatgptREST/.venv/bin/python ops/health_probe.py --fix`
- `chatgptrest-ui-canary.service` is currently broken because its `ExecStart` points to a file that does not exist:
  - `/home/yuanhaizhou/.config/systemd/user/chatgptrest-ui-canary.service`
  - `ExecStart=/vol1/1000/projects/ChatgptREST/.venv/bin/python ops/ui_canary_sidecar.py`

### Partially Confirmed

- `chatgptrest-monitor-12h.service` is in failed state, but the current evidence does not show a live code defect in the script itself.
- A short-window smoke run of `ops/run_monitor_12h.sh` completed successfully when forced to `CHATGPTREST_MONITOR_12H_SECONDS=1` and produced both:
  - `artifacts/monitor/periodic/monitor_12h_20260316_054251Z.jsonl`
  - `artifacts/monitor/periodic/monitor_12h_20260316_054251Z_summary.md`
- Therefore the strongest supported conclusion is:
  - the unit is failed
  - the underlying script is runnable
  - `reset-failed` plus a controlled rerun is reasonable
  - but “only needs reset-failed” was not fully proven by the audit alone

### Rejected / Misdiagnosed

- The claim that “Advisor API (18713) is not running, therefore `/v2/advisor/*` is down” is incorrect.
- Current production behavior shows:
  - `http://127.0.0.1:18711/v2/advisor/health` returns `200 OK`
  - `http://127.0.0.1:18713/v2/advisor/health` returns `404 Not Found` from an Express/Node process
- Port `18713` is currently occupied by GitNexus:
  - `node ... gitnexus/dist/cli/index.js serve --host 127.0.0.1 --port 18713`
- The ChatgptREST application mounts advisor v3 routes into the main API app on port `18711`, not exclusively on a dedicated `18713` listener.
- Evidence:
  - `chatgptrest/api/app.py` includes `make_v3_advisor_router()` in `create_app()`
  - `/v2/advisor/health` is reachable on `18711`

## Evidence

### Advisor routing

- `chatgptrest/api/app.py`
  - advisor v3 router is mounted in the main app factory
- live probe:
  - `GET http://127.0.0.1:18711/v2/advisor/health` -> `200 OK`
  - `GET http://127.0.0.1:18713/v2/advisor/health` -> `404 Not Found`

### Port ownership

- `ss -ltnp` showed:
  - `127.0.0.1:18711` -> `python`
  - `127.0.0.1:18712` -> `python`
  - `127.0.0.1:18713` -> `node`
- `ps -p 2224821 -o pid,ppid,cmd --no-headers` showed:
  - `/home/yuanhaizhou/.nvm/versions/node/v22.22.0/bin/node ... gitnexus/dist/cli/index.js serve --host 127.0.0.1 --port 18713`

### Failed systemd units

- `systemctl --user status chatgptrest-health-probe.service`
  - failed with:
  - `can't open file '/vol1/1000/projects/ChatgptREST/ops/health_probe.py'`
- `systemctl --user status chatgptrest-ui-canary.service`
  - failed with:
  - `can't open file '/vol1/1000/projects/ChatgptREST/ops/ui_canary_sidecar.py'`

## Independent Assessment

### Severity

- `health-probe` broken: High
- `ui-canary sidecar` broken: High
- `monitor-12h` failed state: Medium
- `advisor 18713 port occupancy`: Low as a runtime issue, High as a documentation/config drift issue

### What is actually P0

The real `P0` findings from this audit are the two failed oneshot services whose entrypoint files are missing.

The advisor claim is not a `P0` production outage because the advisor surface is currently served through the main API on `18711`.

## Recommended Actions

1. Restore or replace `ops/health_probe.py`, then restart `chatgptrest-health-probe.service`.
2. Decide whether `ui_canary_sidecar.py` should be restored as an independent sidecar or formally retired in favor of `maint_daemon --enable-ui-canary`.
3. Run:
   - `systemctl --user reset-failed chatgptrest-monitor-12h.service`
   - then execute a short-window rerun before trusting the timer again.
4. Update stale docs and operational expectations that still describe `18713` as the production advisor port.
5. Do not kill the process on `18713` just to “recover advisor”; it is currently used by GitNexus and is not the direct cause of advisor unavailability.

## Final Position

The audit was useful, but mixed valid service regression findings with an incorrect advisor-port diagnosis.

The correct operational summary is:

- advisor v3 is up on `18711`
- GitNexus currently owns `18713`
- two maintenance sidecar services are broken because their target scripts are missing
- the 12h monitor is failed-state dirty, but not yet proven code-broken
