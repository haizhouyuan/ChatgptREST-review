# 2026-04-28 EarlyOOM ChatgptREST Runtime Kill Storm v3

## Why v3 Exists

After the v2 mitigation, monitoring still observed two more earlyoom kills:

- 22:55:47 CST: `node pid=1325835`, which was `gitnexus-mcp-http.service`.
- 22:57:25 CST: `chrome pid=1338192`, the ChatgptREST CDP Chrome main process.

The GitNexus service recovered through systemd restart, but the Chrome kill directly affected the ChatGPT/Gemini Web automation lane until `chatgptrest-chrome.service` restarted Chrome and CDP returned.

## Additional Runtime Mitigation

Changed `/etc/default/earlyoom` outside the repository:

- v2: `-m 5,3`
- v3: `-m 3,2`

Extended earlyoom avoid regex again:

- Added `gitnexus`

Backup:

- `/etc/default/earlyoom.bak_20260428_225818`

Restarted:

- `earlyoom.service`

Immediate runtime hardening:

- Set `oom_score_adj=-100` for current `gitnexus-mcp-http.service` node process.
- Re-applied `oom_score_adj=-100` to all current ChatgptREST service cgroup processes after Chrome watchdog restarted the CDP Chrome tree.

## Validation

After v3 mitigation:

- `chatgptrest-chrome.service` had restarted Chrome.
- `http://127.0.0.1:9226/json/version` returned Chrome CDP metadata.
- `chatgptrest-driver.service` stayed active on port `18701`.
- ChatgptREST API, MCP, dashboard, send worker, wait worker, and Chrome watchdog remained active.
- GitNexus HTTP MCP was active again on port `18713`.

## Follow-Up

This host remains memory-constrained during multi-agent/browser workloads. The durable fix should not be only threshold tuning:

1. Persist lower OOM badness for ChatgptREST and GitNexus critical services through a root-managed slice or another durable mechanism.
2. Identify whether large unrelated `next-server`, Codex, Antigravity, Gemini, and Paperclip processes are expected to coexist during Pro monitoring windows.
3. Keep `earlyoom_recent_kills` in health probe as a first-class signal so future Chrome/CDP or dashboard symptoms are tied back to host memory pressure immediately.
