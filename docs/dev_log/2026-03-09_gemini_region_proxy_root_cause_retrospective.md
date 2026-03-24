# Gemini Region Proxy Root Cause Retrospective

Date: 2026-03-09
Scope: `97356f0..5060102` plus live operations and incident evidence on 2026-03-08/09

## Executive Summary

The stack stayed available, but it was operating in a "repair storm" mode rather than a stable steady state.

The primary recurring fault was Gemini region blocking. The real root cause was not "Gemini unsupported" and not "wrong file upload mode"; it was:

1. `gemini.google.com` was actually routed through the mihomo group `💻 Codex`, not the selector the operator was switching.
2. Browser-side Chrome kept reusing existing Google/Gemini connections after selector changes.
3. Existing diagnostics did not surface the real proxy group / current chain in `repair.check`.
4. Existing autofix paths had no action to switch the Gemini mihomo group.

This pass fixed those gaps in code and docs, then revalidated the live Gemini path.

## What Changed

### Code landed

- `chatgpt_web_mcp/providers/gemini/self_check.py`
  - `gemini_web_self_check()` now classifies browser-side region failures as `GeminiUnsupportedRegion` instead of a generic `RuntimeError`.
  - Successful self-checks now mark `region_supported=true`.
- `chatgpt_web_mcp/providers/gemini_helpers.py`
  - `_gemini_classify_error_type()` now recognizes Chinese region-block messages (`目前不支持你所在的地区`).
- `chatgptrest/ops_shared/infra.py`
  - Added shared mihomo helpers for proxy inspection, selector switch, and connection-chain lookup.
- `chatgptrest/executors/repair.py`
  - `repair.check` now records `Mihomo / Gemini Egress` for Gemini jobs.
  - `repair.autofix` now supports `switch_gemini_proxy`.
  - Gemini region incidents now plan `switch_gemini_proxy -> restart_chrome` in the fallback path.
  - Gemini region faults now auto-escalate to `max_risk=medium` unless the caller pinned a lower risk.
- `chatgptrest/ops_shared/provider.py`
  - Gemini no longer advertises non-existent `gemini_web_blocked_status` / `gemini_web_rate_limit_status` tools in maint/repair paths.

### Docs landed

- `docs/runbook.md`
  - Region section now explains that the real Gemini selector must be verified via mihomo `/connections`.
  - Documented that Chrome restart is mandatory after selector changes.
  - Documented `repair.check` egress report and `repair.autofix` proxy failover knobs.
- `ops/systemd/chatgptrest.env.example`
  - Added `CHATGPTREST_GEMINI_MIHOMO_PROXY_GROUP`, `CHATGPTREST_GEMINI_MIHOMO_CANDIDATES`, and the updated `CHATGPTREST_CODEX_AUTOFIX_ALLOW_ACTIONS`.

### Live config applied

Updated `~/.config/chatgptrest/chatgptrest.env` with:

- `MIHOMO_CONTROLLER_URL=http://127.0.0.1:9090`
- `CHATGPTREST_GEMINI_MIHOMO_PROXY_GROUP=💻 Codex`
- `CHATGPTREST_GEMINI_MIHOMO_CANDIDATES=🇺🇲 美国 01,🇯🇵 日本 03`
- `CHATGPTREST_CODEX_AUTOFIX_ALLOW_ACTIONS=restart_chrome,restart_driver,refresh,regenerate,capture_ui,clear_blocked,switch_gemini_proxy`

## Timeline

### 1. Repeated Gemini region incidents

Gemini region failures were not one-off. They showed up in maint incident packs multiple times:

- [manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/maint_daemon/incidents/20260308_224417Z_1d27d1392ba5/manifest.json)
- [manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/maint_daemon/incidents/20260308_230304Z_9ed46962f25a/manifest.json)
- [manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/maint_daemon/incidents/20260309_001619Z_75d5d813398e/manifest.json)

These were linked with `needs_followup` / UI canary churn rather than a hard global outage.

### 2. Browser-side proof of the region gate

Before the live fix, Gemini rendered the region block in the actual browser page:

- [20260309_081414_gemini_unsupported_region_1428.png](/vol1/1000/projects/ChatgptREST/artifacts/20260309_081414_gemini_unsupported_region_1428.png)
- [20260309_081414_gemini_unsupported_region_1428.html](/vol1/1000/projects/ChatgptREST/artifacts/20260309_081414_gemini_unsupported_region_1428.html)
- [20260309_081414_gemini_unsupported_region_1428.txt](/vol1/1000/projects/ChatgptREST/artifacts/20260309_081414_gemini_unsupported_region_1428.txt)

This mattered because shell-side `curl -x socks5h://127.0.0.1:7890 ...` was not sufficient evidence of what the live Chrome session was actually using.

### 3. Real proxy chain discovery

The critical live finding was that `gemini.google.com` was matching `💻 Codex`, not the selector being manually switched.

That diagnosis came from mihomo `/connections` inspection and browser-side verification, not from generic proxy assumptions.

### 4. Live recovery

The working live fix was:

1. Switch mihomo group `💻 Codex` to `🇺🇲 美国 01`
2. Restart `chatgptrest-chrome.service`

After that, Gemini stopped rendering the region gate and returned to the normal prompt surface.

### 5. Post-fix Gemini smoke

A real human-language Gemini job completed successfully:

- Job: `38d76900dd56492abd3ac356e73fab98`
- Question: `请帮我比较一下 Deep Research 和普通搜索的差别，用 5 句话说给非技术用户。`
- Result: `status=completed`, `answer_chars=376`, `conversation_url=https://gemini.google.com/app/0d24a14683067808`

This proved the live region blocker itself was gone.

### 6. Internal repair validation

External `repair.check` submission over `/v1/jobs` was blocked because the live API currently has no `CHATGPTREST_OPS_TOKEN` configured. That is expected from the route contract and is not a regression in this patch.

To validate the real production repair path, an internal `repair.check` job was created via `chatgptrest/core/repair_jobs.py` and executed by the worker:

- Job: `9531a7a3f1b143599d68c87a2a47920c`
- Then again after the provider tool cleanup:
  - Job: `c9cf7c20c44d44bf83bf6351cbcb2ac3`

The first run proved the new `Mihomo / Gemini Egress` section worked, but also exposed a diagnostic bug: Gemini provider mapping still claimed two non-existent tools. That was fixed in the second code pass.

## Functional Review

### Healthy

- API, Chrome, send workers, wait worker, and maint daemon are all running after the final restart sequence.
- Gemini live ask path is working again after the proxy-group correction.
- Internal `repair.check` can now surface:
  - current Gemini mihomo group
  - current selected node
  - configured failover candidates
  - active Gemini chain
- `repair.autofix` now has a concrete Gemini region action instead of only generic restart/capture fallbacks.

### Not healthy / still noisy

- `active_incidents=55` in `/v1/ops/status`
- Issue DB still shows:
  - `open=21`
  - `mitigated=76`
  - `closed=116`
- Incident DB still shows:
  - `open=55`
  - `resolved=4039`

Current ops snapshot:

- `jobs_by_status`: `completed=5430`, `needs_followup=228`, `error=350`, `blocked=9`, `cooldown=4`
- [latest_report.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/openclaw_guardian/latest_report.json)

This is the key mismatch:

- Guardian latest report says `needs_attention=false`
- But the platform still has `55` open incidents

That means the current guardian summary is too optimistic for operators if they read it as a full health verdict.

## Problems Found During This Pass

### 1. External repair API is not usable on this live host

The live API starts with:

- `No auth tokens configured (CHATGPTREST_API_TOKEN / CHATGPTREST_OPS_TOKEN)`

And external repair jobs fail with:

- `503 repair_kind_ops_token_not_configured`

This affects manual/CLI submission of `repair.check` and `repair.autofix` over `/v1/jobs`.

Important nuance:

- internal maint/worker repair creation still works because it uses `chatgptrest/core/repair_jobs.py` directly against the DB
- this is therefore an operator/API-gap, not a complete auto-repair outage

### 2. Telemetry ingest is generating steady 401 noise

API journal shows repeated:

- `POST /v2/telemetry/ingest HTTP/1.1" 401 Unauthorized`

This appears to be a caller-side auth/config mismatch on loopback traffic, not a server crash, but it creates noise and should be cleaned up.

### 3. Rolling restart behavior is easy to misread

During this pass, `systemctl restart ...` caused the services to enter a prolonged stop/drain cycle, and the API ended up inactive before being explicitly started again.

This did not break data, but it did create a temporary `ConnectionRefusedError` during live validation.

Operationally, this means:

- bulk `restart` is not equivalent to “fast rolling reload”
- the safer pattern on this host is:
  - confirm `send` drain is empty
  - stop/restart in smaller groups
  - verify `is-active` before starting validation

### 4. Guardian summary can hide real backlog

This is a monitoring semantics issue, not a service crash:

- guardian latest report looked green
- incidents and issues remained materially non-zero

This should be corrected in future operator dashboards or summaries.

## Root Cause Chain

The Gemini region problem was caused by a hidden authority split:

1. The operator assumed Gemini followed a human-facing selector (`🚀 节点选择`)
2. The actual routing authority was a different group (`💻 Codex`)
3. Existing diagnostics did not reveal that authority boundary
4. Chrome connection reuse masked selector changes even after the correct group was switched
5. The repair stack therefore had no stable way to propose or apply the real fix

The actual root fix was not “just switch node” and not “just restart Chrome”. It was:

- expose the real proxy authority in diagnostics
- teach the repair stack to act on that authority
- document the validation method so future operators do not debug the wrong group

## Evidence Highlights

- [manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/maint_daemon/incidents/20260308_230304Z_9ed46962f25a/manifest.json)
- [manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/maint_daemon/incidents/20260309_001619Z_75d5d813398e/manifest.json)
- [manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/maint_daemon/incidents/20260309_004415Z_47473ee92e14/manifest.json)
- [manifest.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/maint_daemon/incidents/20260309_005958Z_fc88e9a8396c/manifest.json)
- [latest_report.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/openclaw_guardian/latest_report.json)
- [maint_20260307.jsonl](/vol1/1000/projects/ChatgptREST/artifacts/monitor/maint_daemon/maint_20260307.jsonl)
- [20260309_081414_gemini_unsupported_region_1428.txt](/vol1/1000/projects/ChatgptREST/artifacts/20260309_081414_gemini_unsupported_region_1428.txt)

## Remaining Follow-ups

1. Decide whether this host should configure `CHATGPTREST_OPS_TOKEN`
   - If yes, do it deliberately and validate all callers that hit `/v1/jobs`
   - If no, document that external repair jobs are intentionally unavailable and rely on internal repair creation only
2. Fix or suppress the unauthorized `/v2/telemetry/ingest` loopback caller
3. Tighten guardian summary semantics so “green” cannot coexist silently with dozens of open incidents
4. Consider adding a dedicated Gemini business target into proxy-delay monitoring, but only after reviewing the risk of changing current `mihomo_delay` defaults
