# Full-Route E2E Matrix (Investment Agent Topic) — 2026-02-24

## Scope
- Objective: run a full-route end-to-end validation with a single business prompt:
  - `调研有哪些ai投资tradingagents项目值得参考借鉴用来给我开发个人投资agent项目`
- Repository: `ChatgptREST`
- Build under test: `2807b7830ce4`
- Primary artifact directory:
  - `artifacts/monitor/antigravity_router_e2e/20260224T164939Z/`

## Execution
1. Primary matrix runner:
```bash
PYTHONPATH=. ./.venv/bin/python ops/antigravity_router_e2e.py \
  --include-direct-matrix \
  --cancel-on-timeout \
  --max-wait-seconds 90 \
  --poll-seconds 5 \
  --client-name chatgptrestctl \
  --client-instance codex-e2e-20260224d \
  --topic "调研有哪些ai投资tradingagents项目值得参考借鉴用来给我开发个人投资agent项目" \
  --out-dir artifacts/monitor/antigravity_router_e2e/20260224T164939Z
```

2. Supplemental direct routes (to cover missing paths not included in `antigravity_router_e2e.py`):
- `chatgpt_web.ask` with `preset=auto`
- `chatgpt_web.ask` with `preset=thinking_extended`
- `qwen_web.ask` with `preset=auto`
- `qwen_web.ask` with `preset=deep_thinking`
- `qwen_web.ask` with `preset=deep_research`
- Output files:
  - `artifacts/monitor/antigravity_router_e2e/20260224T164939Z/supplemental_routes_result.json`
  - `artifacts/monitor/antigravity_router_e2e/20260224T164939Z/supplemental_routes_summary.md`

## Result Summary

### A) Primary Matrix (11 cases)
- completed: `2`
- timeout: `8`
- submit_error: `1`

Per-case status:
- `advisor_chatgpt_thinking` -> `timeout` (route observed: `deep_research`)
- `advisor_chatgpt_pro_extended` -> `timeout` (route observed: `pro_then_dr_then_pro`)
- `advisor_deep_research` -> `timeout`
- `advisor_pro_then_dr_then_pro` -> `timeout`
- `advisor_gemini_pro` -> `submit_error`
- `advisor_crosscheck` -> `timeout`
- `direct_chatgpt_thinking_heavy` -> `timeout`
- `direct_chatgpt_pro_extended` -> `timeout`
- `direct_chatgpt_deep_research` -> `timeout`
- `direct_gemini_pro` -> `completed` (`answer_chars=1836`)
- `direct_gemini_deep_think` -> `completed` (`answer_chars=108`)

### B) Supplemental Direct Routes (5 cases)
- cooldown: `3`
- timeout: `1`
- submit_error: `1`

Per-case status:
- `direct_chatgpt_auto` -> `cooldown`
- `direct_chatgpt_thinking_extended` -> `timeout`
- `direct_qwen_auto` -> `cooldown`
- `direct_qwen_deep_thinking` -> `cooldown`
- `direct_qwen_deep_research` -> `submit_error`

## Findings (RCA-oriented)

1. Advisor route selection deviated from expected route labels for chatgpt-focused cases.
- Evidence:
  - `cases/01_advisor_chatgpt_thinking.json` -> route observed `deep_research`
  - `cases/02_advisor_chatgpt_pro_extended.json` -> route observed `pro_then_dr_then_pro`
- Impact: route contract predictability is weak under this prompt/context.

2. ChatGPT path stability is currently limited in this environment (high timeout ratio).
- Evidence: 8 timeouts in primary matrix; supplemental `thinking_extended` also timeout.
- Impact: full-route throughput not stable for chatgpt paths under short bounded wait windows.

3. Gemini direct path is currently the only route that reliably completed in this batch.
- Evidence: `direct_gemini_pro` and `direct_gemini_deep_think` both completed.

4. Qwen `deep_research` validation is inconsistent.
- Evidence (`supplemental_routes_result.json`):
  - HTTP 400 detail: `unsupported params.preset for qwen_web.ask: 'deep_research'`
  - Same error body lists `supported: ["auto","deep_research","deep_thinking"]`
- Impact: contract contradiction; likely server-side preset validation bug or normalization bug.

5. Cooldown cases exposed infra-level reason in job reason field.
- Evidence (`jobs get f5e153...` during cleanup):
  - `CDP connect failed ... CDP fallback is disabled ...`
- Impact: route-level reliability is coupled to browser/CDP availability; this should surface as explicit client-facing retry policy.

## Final Assessment
- Full-route matrix execution: **completed (16/16 cases executed with terminal outcomes recorded)**.
- Business readiness for chatgpt-heavy route mix: **not yet stable**.
- Fastest usable path in current environment: **Gemini direct routes**.

## Evidence Pointers
- Main matrix raw: `artifacts/monitor/antigravity_router_e2e/20260224T164939Z/result.json`
- Main matrix summary: `artifacts/monitor/antigravity_router_e2e/20260224T164939Z/summary.md`
- Case details: `artifacts/monitor/antigravity_router_e2e/20260224T164939Z/cases/*.json`
- Supplemental raw: `artifacts/monitor/antigravity_router_e2e/20260224T164939Z/supplemental_routes_result.json`
- Supplemental summary: `artifacts/monitor/antigravity_router_e2e/20260224T164939Z/supplemental_routes_summary.md`
