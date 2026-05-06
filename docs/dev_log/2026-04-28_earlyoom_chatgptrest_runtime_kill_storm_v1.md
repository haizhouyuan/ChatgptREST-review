# 2026-04-28 EarlyOOM ChatgptREST Runtime Kill Storm

## Context

During a 10 hour client-usage watch, multiple ChatGPT Pro / Deep Research jobs failed before `prompt_sent_at`. The visible symptoms looked like ChatGPT Web automation failures:

- `TargetClosedError: Locator.count: Target page, context or browser has been closed`
- `BrowserType.launch: Connection closed while reading from the driver`
- ChatgptREST API and dashboard repeatedly logged Uvicorn `Shutting down`
- Chrome CDP on `127.0.0.1:9226` disappeared

These were not caused by a fresh ChatGPT 429 at the time of investigation.

## Root Cause

The root cause was host memory pressure interacting with the system `earlyoom` policy.

Evidence:

- `free -h` showed roughly 30 GiB RAM, 26 GiB used, about 4.5-5.1 GiB MemAvailable, and 8.9 GiB swap used.
- `/usr/bin/earlyoom` was running with `-m 16,10 -s 100,100`, which starts killing when MemAvailable falls below about 4.9 GiB on this host.
- `/var/log/earlyoom/earlyoom_kills_2026-04-28.log` recorded kills for:
  - `python` under `chatgptrest-dashboard.service`
  - `chrome`
  - `npm exec @playw...`
  - `next-server`
  - `node`
- ChatgptREST user services had `OOMScoreAdjust=200`, producing `oom_score=800` for API, driver, MCP, send worker, wait worker, and Chrome watchdog.

The API/dashboard `Shutting down` messages were graceful SIGTERM handling after earlyoom selected those processes. The Chrome CDP failures and Playwright driver disconnections were downstream effects.

## Runtime Impact

Affected current jobs:

- `12f9e4efdf824087823834c101e28916`: failed repeatedly before `prompt_sent_at` with `TargetClosedError`; later canceled by another client as superseded.
- `8441c085bdc349dabc60dbfc0f6c04e6`: fallback Pro job failed in send with `BrowserType.launch: Connection closed while reading from the driver`.

No usable Pro answer was produced by those jobs.

## Mitigation Applied

Changed `/etc/default/earlyoom` outside the repository:

- Before: `-m 16,10`
- After: `-m 10,5`

Rationale:

- On this 30 GiB host, `-m 16` caused kill storms while several GiB were still available.
- `-m 10,5` keeps earlyoom as a safety net but avoids killing browser/API control-plane processes during normal agent memory bursts.

Backup:

- `/etc/default/earlyoom.bak_20260428_220311`

Then restarted:

- `earlyoom.service`
- `chatgptrest-chrome.service`
- `chatgptrest-driver.service`

Also cleared stale Chrome profile locks from:

- `secrets/chrome-profile/SingletonLock`
- `secrets/chrome-profile/SingletonSocket`
- `secrets/chrome-profile/SingletonCookie`

Runtime evidence captured under:

- `artifacts/monitor/client_usage_watch_10h/20260428_134529Z/runtime_fixes/`

## Validation

After mitigation:

- `127.0.0.1:9226/json/version` returned Chrome CDP metadata.
- `18701`, `18711`, `18712`, and `8787` were listening.
- `chatgptrest-api.service`, `chatgptrest-mcp.service`, `chatgptrest-driver.service`, `chatgptrest-worker-send.service`, `chatgptrest-worker-wait.service`, `chatgptrest-chrome.service`, and `chatgptrest-dashboard.service` were active.
- The send pause was cleared with reason `codex_monitor:earlyoom_threshold_lowered_cdp_recovered_clear_send_pause`.
- The 10 hour monitor saw no new problem events in cycles 20-24 after the recovery.

## Follow-Up

This event shows that ChatGPT Web failures can be secondary symptoms of host memory policy. Future incident triage should check earlyoom logs and OOM scores before attributing `TargetClosedError`, `Page crashed`, or repeated Uvicorn shutdowns to ChatGPT Web, Cloudflare, or 429.

If this recurs, consider a narrower systemd-level solution:

- Reduce default user service `OOMScoreAdjust` for critical ChatgptREST units.
- Add dedicated systemd drop-ins for ChatgptREST API, driver, MCP, workers, and Chrome watchdog if user-manager permissions allow it.
- Add monitor alerts for new `/var/log/earlyoom/earlyoom_kills_*.log` entries that mention `chatgptrest`, `chrome`, `playwright`, `python`, or `next-server`.
