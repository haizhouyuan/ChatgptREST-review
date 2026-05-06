# 2026-04-28 EarlyOOM ChatgptREST Runtime Kill Storm v2

## What Changed Since v1

The first mitigation lowered `/etc/default/earlyoom` from `-m 16,10` to `-m 10,5`.
Continued monitoring showed that this was still too aggressive for the live host:

- At about 22:20-22:21 CST, `chatgptrest-dashboard.service` was still killed repeatedly.
- `/var/log/earlyoom/earlyoom_kills_2026-04-28.log` showed fresh `python` kills from the dashboard cgroup.
- `free -h` showed about 3.0-3.7 GiB MemAvailable, not a true last-resort OOM condition for this 30 GiB host.
- API, MCP, driver, send worker, wait worker, Chrome watchdog, and dashboard processes inherited `oom_score_adj=200`, producing high `oom_score` values around 800.

## Updated Root Cause

The incident was not just a high earlyoom memory threshold. The full cause was:

1. The host was under sustained memory pressure from multiple agent/browser/node workloads.
2. earlyoom had swap gating configured as `-s 100,100`, so the swap condition was effectively always true once swap was used.
3. ChatgptREST user services inherited high OOM badness from the user service manager.
4. earlyoom therefore selected ChatgptREST control-plane processes even while several GiB of memory remained available.

This made ChatGPT Web automation failures look like `TargetClosedError`, driver disconnects, dashboard connection refusals, or Uvicorn shutdowns.

## Second Mitigation Applied

Changed `/etc/default/earlyoom` outside the repository:

- Before v1: `-m 16,10`
- v1: `-m 10,5`
- v2: `-m 5,3`

Also extended the earlyoom avoid regex:

- Added `chatgptrest`
- Added `ChatgptREST`
- Added `chrome-profile`

Backup:

- `/etc/default/earlyoom.bak_20260428_222148`

Restarted:

- `earlyoom.service`

Immediate runtime hardening:

- Set `oom_score_adj=-100` for the currently running ChatgptREST service cgroup processes, including API, MCP, driver, send worker, wait worker, dashboard, Chrome watchdog, and Chrome children.
- Granted `yuanhaizhou` traverse/read ACLs for `/var/log/private/earlyoom` and the current daily earlyoom log so user-level health probes can read the sanitized postkill log.
- Added `earlyoom_recent_kills` to `ops/health_probe.py`; it reports any earlyoom kills from the last 15 minutes as a first-class health attention item.

## Validation

After v2 mitigation:

- `ops/health_probe.py --fix --json` returned `rc=0`.
- `api_18711`, `mcp_18712`, `dashboard_8787`, `jobdb`, `kb_fts`, `memory`, `public_mcp_ingress_contract`, and `maintenance_timers` were all OK.
- `stuck_jobs` was OK with one remaining old `needs_followup` item.
- `chatgptrest-dashboard.service` was active and `/health` returned `startup=ready`.
- The monitoring supervisor returned to `abnormal_recent=0`.
- After adding the earlyoom health item, `ops/health_probe.py --fix --json` intentionally returned `rc=1` while the 22:20-22:21 kill storm was still inside the 15 minute window. This is correct telemetry, not a fresh service failure.

## Follow-Up

The runtime `oom_score_adj=-100` writes are immediate but not durable across process restart. The durable part is the earlyoom threshold and avoid-regex change.

If kill storms recur, next fixes should be evaluated in this order:

1. Reduce memory load from unrelated large node/browser workloads if they are no longer needed.
2. Move ChatgptREST critical services into a root-managed slice or otherwise persist a lower OOMScoreAdjust.
3. Revisit `-s 100,100`; it intentionally ignores swap gating but can make earlyoom too eager when swap is chronically used.
4. Keep monitoring `/var/log/earlyoom/earlyoom_kills_*.log` as a first-class incident source, not a postmortem-only artifact.
