# Antigravity Router E2E Matrix (2026-02-24)

## Goal

Run one end-to-end matrix for the same EvoMap topic across:
- advisor route selection (`chatgpt_pro`, `deep_research`, `pro_then_dr_then_pro`, `gemini`, `pro_gemini_crosscheck`)
- optional direct provider presets (`chatgpt_web.ask` thinking/pro/deep_research, `gemini_web.ask` pro/deep_think)

Target question theme:
- 给 Codex 配上 EvoMap，让代理具备“自净化（异常检测 -> 策略修复 -> 证据回灌）”能力。

## Runner

Script:
- `ops/antigravity_router_e2e.py`

Key behavior:
- each case submits a real live job (`/v1/advisor/advise` or `/v1/jobs`)
- waits to terminal state with bounded deadline
- optional timeout cancel with `X-Cancel-Reason`
- writes per-case JSON + run summary markdown

Output directory:
- `artifacts/monitor/antigravity_router_e2e/<timestamp>/`

## Commands

Advisor-only matrix:

```bash
PYTHONPATH=. ./.venv/bin/python ops/antigravity_router_e2e.py \
  --max-wait-seconds 1800 \
  --poll-seconds 15 \
  --cancel-on-timeout
```

Full matrix (advisor + direct presets):

```bash
PYTHONPATH=. ./.venv/bin/python ops/antigravity_router_e2e.py \
  --include-direct-matrix \
  --max-wait-seconds 2400 \
  --poll-seconds 15 \
  --cancel-on-timeout
```

Run subset:

```bash
PYTHONPATH=. ./.venv/bin/python ops/antigravity_router_e2e.py \
  --cases advisor_chatgpt_thinking,advisor_gemini_pro \
  --max-wait-seconds 900 \
  --cancel-on-timeout
```

Custom EvoMap question:

```bash
PYTHONPATH=. ./.venv/bin/python ops/antigravity_router_e2e.py \
  --topic "请分析 EvoMap 如何接入 Codex 自净化闭环，并给出 owner/next_owner/ETA/blocker/evidence_path" \
  --include-direct-matrix \
  --max-wait-seconds 2400 \
  --cancel-on-timeout
```

## Validation Snapshot

Single-case live sample was executed:
- case: `advisor_chatgpt_thinking`
- output: `artifacts/monitor/antigravity_router_e2e/20260224T154220Z/`
- route check: `route_match=true`, `kind_match=true`
- final status: `timeout` (bounded run with auto-cancel enabled)

Notes:
- timeout is expected when wait budget is short or queue interval is active.
- summary artifacts still capture route selection correctness and submit/wait/cancel behavior.
