# 2026-03-09 Runtime Retrospective: Gemini region repair, provider reload, and live health review

## Scope

This retrospective covers the period from the Gemini region repair landing through the later live validation and provider health sweep on 2026-03-09.

Primary code/doc changes already in the tree before this write-up:

- `025c273` `fix(gemini): add region-aware repair probes and autofix`
- `39b02e1` `docs(ops): record gemini proxy root cause retrospective`

Concurrent repo movement observed during live validation:

- local HEAD moved from `39b02e1` to `3fc9265`
- later `/v1/ops/status` reported live build `347e32410ff2`

This matters operationally: code review conclusions below are based on the actual live behaviors observed, not just the commit that initially introduced the Gemini repair logic.

## What Was Changed And Applied

### Repo changes already landed

- Gemini `repair.check` / `repair.autofix` now understand region-block symptoms and mihomo proxy groups.
- `gemini_web_self_check` now returns explicit `region_supported` signal when the page shows unsupported-region text.
- bogus Gemini blocked/rate-limit tool mappings were removed from `chatgptrest/ops_shared/provider.py`.

### Live config changes applied during this session

Updated `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`:

- `MIHOMO_CONTROLLER_URL=http://127.0.0.1:9090`
- `CHATGPTREST_GEMINI_MIHOMO_PROXY_GROUP=💻 Codex`
- `CHATGPTREST_GEMINI_MIHOMO_CANDIDATES=🇺🇲 美国 01,🇯🇵 日本 03`
- `CHATGPTREST_CODEX_AUTOFIX_ALLOW_ACTIONS=restart_chrome,restart_driver,refresh,regenerate,capture_ui,clear_blocked,switch_gemini_proxy`
- `CHATGPTREST_QWEN_ENABLED=1`

Operational actions applied:

- switched mihomo `💻 Codex` to `🇺🇲 美国 01`
- restarted `chatgptrest-chrome.service`
- restarted `chatgptrest-worker-send-gemini@0..3.service`
- restarted `chatgptrest-worker-send.service`
- restarted `chatgptrest-worker-send-qwen.service`
- started dedicated Qwen Chrome via `bash ops/qwen_chrome_start.sh`

## Timeline

### 1. Gemini region issue reproduced and root-caused

Evidence:

- `artifacts/20260309_073403_gemini_unsupported_region_1520.png`
- `artifacts/20260309_073403_gemini_unsupported_region_1520.html`
- `artifacts/20260309_073403_gemini_unsupported_region_1520.txt`
- `artifacts/20260309_081414_gemini_unsupported_region_1428.png`
- `artifacts/20260309_081414_gemini_unsupported_region_1428.html`
- `artifacts/20260309_081414_gemini_unsupported_region_1428.txt`

Observed root cause chain:

1. `gemini.google.com` traffic actually matched mihomo group `💻 Codex`, not `🚀 节点选择`.
2. Chrome reused existing Google/Gemini connections, so selector changes alone appeared ineffective.
3. Browser-side proof showed the real error, not a speculative proxy guess.

### 2. Gemini region fix validated live

Successful Gemini smoke evidence:

- job `38d76900dd56492abd3ac356e73fab98`
- job `6c54d29552c749a5bad8d021556f63cc`

Observed behavior:

- both jobs completed on `kind=gemini_web.ask`
- both returned meaningful Chinese answers to a real human-language question about Deep Research vs ordinary search
- one sample answer path: `artifacts/jobs/6c54d29552c749a5bad8d021556f63cc/answer.md`

### 3. `repair.check` first looked stale after the code fix

First validation still showed:

- `Unknown tool: gemini_web_blocked_status`
- `Unknown tool: gemini_web_rate_limit_status`

Evidence:

- job `aa498ddee69c4454accf9d0fd31860b0`
- `artifacts/jobs/aa498ddee69c4454accf9d0fd31860b0/repair_report.json`

This turned out **not** to be a code regression. The live executor was still served by an old generic send worker process.

### 4. Generic send worker reload fixed stale `repair.check`

After restarting `chatgptrest-worker-send.service`, the same validation passed:

- job `a9e6a4f516c84d29b082edc3b9cb4b4e`
- `artifacts/jobs/a9e6a4f516c84d29b082edc3b9cb4b4e/repair_report.json`

Verified result:

- `Driver Probe -> ok: True`
- `Mihomo / Gemini Egress` rendered correctly
- group `💻 Codex`
- node `🇺🇲 美国 01`
- chain `🇺🇲 美国 01 -> 💻 Codex`

### 5. Qwen health sweep separated fake failure from real failure

Initial Qwen failures:

- job `16830886845a454eb8b3a467b1dba826`
- job `14dc16ac29da4653b1aa9a6c177316b2`

Both failed with:

- `ValueError: Unknown job kind: qwen_web.ask`

Root cause:

- `CHATGPTREST_QWEN_ENABLED` was missing in live env
- the generic send worker was still able to claim `qwen_web.ask`

After setting `CHATGPTREST_QWEN_ENABLED=1` and restarting both generic and Qwen send workers, the false failure disappeared.

Intermediate true failure:

- job `9c9e7a64aa3f4a7abe645ddb85567a68`
- `error_type=InfraError`
- `Qwen CDP connect failed`

That was a real infra issue: Qwen Chrome was not running.

After starting dedicated Qwen Chrome, the next Qwen smoke reached the next true state:

- job `7b59024f91e449e598004d64497a88ee`
- `status=needs_followup`
- `_QwenNotLoggedInError`

Evidence:

- `artifacts/jobs/7b59024f91e449e598004d64497a88ee/result.json`
- `artifacts/jobs/7b59024f91e449e598004d64497a88ee/events.jsonl`
- `artifacts/jobs/7b59024f91e449e598004d64497a88ee/run_meta.json`

Conclusion: the Qwen path is now routing correctly; the remaining issue is an operator/browser-profile login prerequisite, not an executor lookup bug.

### 6. ChatGPT smoke accepted and reached wait/export reconciliation

ChatGPT smoke job:

- `1767cdf658a346e9bffe679cfe06d68b`

Observed live state at snapshot time:

- `status=in_progress`
- `phase=wait`
- `phase_detail=awaiting_export_reconciliation`
- `conversation_export_path=jobs/1767cdf658a346e9bffe679cfe06d68b/conversation.json`

This is not a hard failure, but it remained unfinished at the snapshot point and should be treated as a slow-path item, not a clean pass.

## Function-By-Function Review

### Healthy / verified

- Gemini send path: healthy after proxy group correction and Chrome restart
- Gemini repair diagnostics: healthy after generic send worker reload
- API main surface: reachable and serving `/v1/ops/status`
- maint daemon: running and still generating incident / repair evidence
- guardian: latest report `ok=true`, `needs_attention=false`
- UI canary: latest report green for both ChatGPT and Gemini

Key evidence:

- `artifacts/monitor/openclaw_guardian/latest_report.json`
- `artifacts/monitor/ui_canary/latest.json`

### Healthy but with operator prerequisites

- Qwen executor path: healthy after env + worker reload
- Qwen runtime prerequisites: not fully satisfied
  - first missing dedicated Chrome
  - then missing Qwen login in the profile

### Not clean yet

- ChatGPT sample job is still waiting on export reconciliation
- incident ledger still contains old Gemini-region and stale stuck-job incidents even though current live canary is green
- issue ledger still contains old `Unknown job kind: qwen_web.ask` records from before the env/worker fix

## Problems Found In Logs

### 1. Repeated `401 Unauthorized` on `/v2/telemetry/ingest`

Symptoms:

- repeated loopback requests to `/v2/telemetry/ingest` and sometimes `/v2/context/resolve`
- API returns `401 Unauthorized`

Evidence:

- `journalctl --user -u chatgptrest-api.service --since '2026-03-09 08:00:00'`

Interpretation:

- this is not a core queue outage
- it is an integration/auth mismatch on the OpenMind v2 side
- the noise is high enough to pollute logs and can obscure other incidents

### 2. Viewer watchdog keeps reporting left-over processes

Symptoms:

- repeated `Found left-over process ... in control group while starting unit`
- repeated `Unit process ... remains running after unit stopped`

Evidence:

- `journalctl --user -u chatgptrest-viewer-watchdog.service --since '2026-03-09 09:20:00'`

Interpretation:

- viewer path is not currently broken
- service hygiene is poor and restart semantics are leaky

### 3. Maint / guardian surfaces are not fully aligned

Evidence:

- `artifacts/monitor/openclaw_guardian/latest_report.json`
- `artifacts/monitor/openclaw_orch/latest_report.json`
- `artifacts/monitor/ui_canary/latest.json`

Observed mismatch:

- guardian reports `needs_attention=false`
- orch report still reports `needs_attention=true` with `reconcile_not_ok`
- ui_canary is green
- active incidents remain high (`55`)

Interpretation:

- the system is operational
- the management-plane summary is not yet coherent

### 4. Client-side contract drift is causing avoidable smoke failures

Observed:

- missing `Idempotency-Key` header returns HTTP `422`
- `X-Client-Name=codex` is rejected by allowlist with HTTP `403`
- `chatgpt_web.ask` no longer accepts `preset=pro`
- `qwen_web.ask` requires explicit preset and provider enable flag

These are not hidden bugs, but they are easy to misdiagnose if the caller is using old habits.

## Current Snapshot

Final live snapshot during this retrospective:

- `/v1/ops/status`
  - `build.git_sha=347e32410ff2`
  - `jobs_by_status={"blocked":9,"canceled":245,"completed":5436,"cooldown":4,"error":353,"in_progress":5,"needs_followup":230}`
  - `active_incidents=55`
- guardian latest report:
  - `ok=true`
  - `needs_attention=false`
- orch latest report:
  - `ok=false`
  - `needs_attention=true`
  - `attention_reasons=["reconcile_not_ok"]`

## Concrete Conclusions

1. The Gemini region repair itself is successful.
2. The new repair diagnostics are successful, but only after reloading the **generic** send worker.
3. Qwen was not broken in code; it was first disabled by env drift, then blocked by missing Qwen Chrome, then blocked by missing Qwen login.
4. The biggest remaining operational problems are:
   - noisy unauthorized OpenMind v2 telemetry/context writes
   - stale issue/incident records that no longer represent current live state
   - viewer watchdog process hygiene
   - orch reconcile drift
   - ChatGPT slow-path export reconciliation not yet closed on the sample smoke

## Follow-Ups

Recommended next actions, in order:

1. Mitigate / close stale Gemini region incidents and stale `Unknown job kind: qwen_web.ask` issues now that the real live state is known.
2. Fix the source of repeated `/v2/telemetry/ingest` `401` loopback calls.
3. Login once in the dedicated Qwen profile (`qwen_viewer_start.sh` / noVNC) and rerun `qwen_web.ask` smoke.
4. Clean up `viewer-watchdog` left-over process hygiene.
5. Reconcile `openclaw_orch` so guardian/orch/ui_canary do not disagree on top-level health.
