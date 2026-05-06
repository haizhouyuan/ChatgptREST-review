# API Direct Call Audit (2026-02-27)

## Scope
- Audit time: 2026-02-27 (UTC)
- Windows analyzed:
  - recent: last 24h (event attribution + API journal)
  - trend: last 30 days (job DB + issue ledger)
  - lifetime baseline: 2025-12-26 to 2026-02-27 (job DB)

## Data sources
- `state/jobdb.sqlite3` (`jobs`, `job_events`, `client_issues`)
- `journalctl --user -u chatgptrest-api.service`
- `artifacts/jobs/*/events.jsonl`

## Key findings

### 1) API direct usage quality (24h)
- `job_created/cancel_requested` attribution events: 68
- `job_created` by client:
  - `chatgptrest-mcp`: 36
  - `chatgptrestctl`: 12
  - `<none>`: 17
- `cancel_requested` by client:
  - `chatgptrestctl`: 3
- `chatgptrestctl` trace header completeness:
  - `x_client_instance`: 100% present (12 creates + 3 cancels)
  - `x_request_id`: 100% present (12 creates + 3 cancels)

Interpretation:
- direct CLI/API writes are mostly traceable now.
- observed `/cancel` mistakes are policy-caught (403/409), not silent.

### 2) `<none>` attribution is mostly internal workload, not external leak
- Last 24h `<none>` job_created = 17
- All 17 are `repair.check` with `client_json.name=maint_daemon` (internal maintenance path)

Interpretation:
- these are internal jobs lacking HTTP header identity, not arbitrary external API writes.
- observability is still weaker for these internal flows (client identity appears as `<none>`).

### 3) API non-200 write profile (journal retained window)
- `POST /v1/jobs`:
  - 200: 57
  - 400: 4
  - 403: 2
- `POST /v1/jobs/{id}/cancel`:
  - 200: 5
  - 403: 5
  - 409: 2

Interpretation:
- most failures are expected policy blocks (`allowlist`, `missing/blocked cancel reason`), indicating guardrails are effective.

### 4) 30-day trend: cancellation and status pressure
- 30-day jobs: 2216
- by client:
  - `chatgptrest-mcp`: 1375
  - `<none>`: 781
  - `chatgptrestctl`: 53
  - `e2e-test`: 7
- `chatgptrestctl` 30-day status split:
  - completed: 19
  - canceled: 26
  - error: 7
  - needs_followup: 1

Interpretation:
- direct CLI/API calls exist but are not dominant in volume.
- direct CLI cancel ratio is high (mostly orchestration cleanup/timeouts), so cancel policy must stay strict.

### 5) Cancellation semantics quality (30-day)
- cancel events: 177
- reason distribution:
  - `<none>`: 138 (mostly historical `chatgptrest-mcp` path)
  - `chatgptrestctl_manual_cancel`: 4
  - others are specific reasons (`antigravity_timeout:*`, `e2e_*`, etc.)

Interpretation:
- historical cancel reason quality is uneven.
- recent generic default reason has already been blocked by policy.

### 6) Longer-horizon systemic debt
- lifetime jobs: 4181
- non-terminal backlog currently: 208
  - `needs_followup`: 194
  - `blocked`: 9
  - `cooldown`: 4
  - `in_progress`: 1
- stale distribution:
  - stale >24h: 205+
  - stale >7d: 167+

Interpretation:
- biggest operational debt is stale non-terminal accumulation, not only direct API misuse.

## Deeper reflection

1. Guardrails are now effective at blocking bad writes, but post-block observability is incomplete on create-path rejects.
2. Identity model is mixed: some callers use HTTP with strong trace headers, while internal jobs still appear as `<none>`.
3. Cancel behavior historically mixed cleanup/test semantics with production semantics, causing noisy cancellations and harder RCA.
4. The largest reliability risk is aging `needs_followup` backlog: unresolved long-tail jobs dilute signal and increase recurring confusion.

## Priority actions

P0:
- Add auto-issue reporting for `POST /v1/jobs` policy rejects (same model as cancel policy auto-report).
- Separate/label non-HTTP internal job identity explicitly (avoid `<none>` attribution blind spot).

P1:
- Enforce stricter client identity semantics for "MCP identity" (prevent direct scripts from mimicking MCP identity in headers).
- Add daily API quality report:
  - create/cancel 2xx/4xx/5xx
  - cancel reason quality
  - trace header coverage

P2:
- Run stale backlog janitor for old `needs_followup/blocked/cooldown` with explicit close/mitigate policy and evidence notes.

## Current open issues snapshot
- `iss_50c9914f35a84bbe8d38ffd751c62cd9` (`worker_auto`, `gemini_web.ask needs_followup: RuntimeError`)
- `iss_2475017189fa472da20688126cfe98f9` (`antigravity` client bug)

## Extended window update (2026-02-27 15:00 CST)

### A) Job outcome pressure by time window (from `jobs`)
- 6h: `jobs=19`, `error=0`, `canceled=3`, `nonterminal=1`
- 24h: `jobs=65`, `error=1`, `canceled=3`, `nonterminal=2`
- 7d: `jobs=943`, `error=35`, `canceled=112`, `nonterminal=10`
- 30d: `jobs=2216`, `error=114`, `canceled=138`, `nonterminal=52`

Interpretation:
- “最近几小时”失败率并不高，但 7d/30d 仍有结构性错误簇（不是偶发单点）。

### B) 7d/30d 主要失败簇（`status=error` 的 `last_error_type`）
- 7d top: `MaxAttemptsExceeded=9`, `NameError=8`, `RuntimeError=7`, `ValueError=5`, `Error=4`
- 30d top: `MaxAttemptsExceeded=36`, `RuntimeError=16`, `Error=15`, `AttributeError=9`, `NameError=8`, `ValueError=7`, `UnboundLocalError=7`

Interpretation:
- 失败主因并非单一“API 调错”，而是三类叠加：
  1) UI/driver 易碎性（`RuntimeError/Error/MaxAttemptsExceeded`）
  2) 代码回归缺口（`NameError/UnboundLocalError/AttributeError`）
  3) 输入契约错误（`ValueError`）

### C) MCP 侧近窗失败留痕（`artifacts/monitor/mcp_http_failures.jsonl`）
- 当前累计 `4` 条（全部来自 `chatgptrest-mcp`）：
  - `mcp_api_cancel_forbidden` (403) = 2
  - `mcp_transport` (connection refused) = 1
  - `HTTP 409 answer not ready`（非 policy 失败）= 1

Interpretation:
- MCP 主链路当前失败量低，但“被策略拒绝”已有复发样本，说明需要把 create/cancel 统一纳入 issue 闭环（而不是只在日志中看见）。

## Optimization/deep-reflection conclusions

1. 仅靠“人工看日志”无法阻断复发：拒绝类 4xx 必须自动入账（issue ledger），否则同类错误在新 agent 会再次出现。  
2. 过去 30d 的错误结构显示“代码回归 + UI 易碎 + 输入契约”并存，单独优化某一条链路不足以消除复发。  
3. 非终态历史债务（`needs_followup/blocked/cooldown`）仍是噪音源，会掩盖新问题，必须持续 janitor + 退出机制。  

## Immediate rollout applied (online)

- `POST /v1/jobs` create-path 策略拒绝已接入自动 issue 上报（`source=api_policy`,`kind=create_policy`）：
  - 覆盖：`client_not_allowed`、`missing_trace_headers`、`pro_smoke_test_blocked`、`trivial_pro_prompt_blocked`、`smoke_test_blocked`、`idempotency_collision`
  - 验证：2026-02-27 15:07 CST 实际触发 `client_not_allowed`，自动写入并可查询 issue；随后人工关闭验证 issue，避免污染看板。
