# 2026-03-31 Research Finality And Runtime Governance Fix Walkthrough v1

## 本次收口的两个问题

1. research 长答案 finality 仍可能被旧 job 错投影为 final
2. live 运行面里 dead timer + stale blocked jobs 让服务体感像“不可用”

## 代码修复

提交：`43f7e24` `Harden research finality and stale job cleanup`

### 1. research finality 改成语义优先

- `chatgptrest/api/routes_jobs.py`
  - `job_events` 汇总现在保留 `completion_guard_*` 语义，不再单纯 `latest-event-wins`
  - `completed_under_min_chars` / `research_contract_blocked` 会压过后续普通 `status_changed`
  - `/v1/jobs/{job_id}/answer` 现在按 `completion_contract.answer_state` + `canonical_answer.ready` gate
  - 非 final parent job 如果同会话存在后续 final child，会解析出：
    - `authoritative_job_id`
    - `authoritative_answer_path`
    - `action_hint=fetch_authoritative_answer`

- `chatgptrest/core/completion_contract.py`
  - durable contract/canonical answer 新增 `authoritative_job_id`
  - `conversation_authoritative_resolution` 会写入 provenance

- `chatgptrest/mcp/server.py`
  - MCP `chatgptrest_result(...)` 现在把 authoritative child 明确返回给调用方

### 2. stale intermediate jobs 不再无限挂着

- `chatgptrest/core/job_store.py`
  - `request_cancel(...)` 对 `needs_followup` / `blocked` / `cooldown` 直接终态化为 `canceled`
  - 不再只写 `cancel_requested_at` 然后长期残留

- `ops/backlog_janitor.py`
  - 新增 stale job cleanup，能把长期 `blocked/needs_followup/cooldown` 收成 `error`
  - 同步补 DB event、artifact event 和 `result.json`

- `ops/health_probe.py`
  - 新增 `maintenance_timers` 检查
  - 现在会明确报：
    - `chatgptrest-health-probe.timer`
    - `chatgptrest-backlog-janitor.timer`
    - `chatgptrest-ui-canary.timer`
    是否活着

### 3. attachment contract 误判收紧

- `chatgptrest/core/attachment_contract.py`
  - `/importer/review`、`episodic/semantic/procedural` 这类 slash 概念词不再被误当成本地文件
  - 真正 rooted/relative/bundle path 的 fail-closed 仍保留

## 测试

执行：

```bash
./.venv/bin/pytest -q \
  tests/test_attachment_contract_preflight.py \
  tests/test_job_view_progress_fields.py \
  tests/test_mcp_unified_ask_min_chars.py \
  tests/test_leases.py \
  tests/test_backlog_janitor.py \
  tests/test_health_probe.py \
  tests/test_contract_v1.py \
  tests/test_worker_and_answer.py \
  tests/test_chatgpt_agent_shell_v0_turn_guard.py \
  tests/test_cli_chatgptrestctl.py \
  tests/test_cancel_attribution.py \
  tests/test_check_public_mcp_client_configs.py
```

结果：`exit code 0`

## live 动作

执行：

```bash
systemctl --user restart \
  chatgptrest-api.service \
  chatgptrest-mcp.service \
  chatgptrest-worker-send.service \
  chatgptrest-worker-wait.service

systemctl --user enable --now \
  chatgptrest-health-probe.timer \
  chatgptrest-backlog-janitor.timer \
  chatgptrest-ui-canary.timer

python3 ops/backlog_janitor.py \
  --apply \
  --job-stale-hours 1 \
  --issue-stale-hours 72 \
  --job-limit 200 \
  --job-max-updates 200

python3 ops/health_probe.py --json
```

结果：

- 3 个 maintenance timer 从 `inactive/dead` 变为 `active/waiting`
- janitor 一次性终态化 `14` 个 stale jobs
- `health_probe --json` 现在：
  - `stuck_jobs.ok = true`
  - `stuck_count = 0`
  - `maintenance_timers.ok = true`
  - `all_ok = true`

## 结论

- 研究类 job 现在不会再因为旧 parent 已 `completed` 就被误判为 final 正式答案
- live 运行治理不再靠人工盯：timer 活着，janitor 能自动收 stale intermediate jobs
- attachment preflight 不再把 slash 概念词误判成文件路径

## 本次未做

- 没有重新跑真实 ChatGPT 长研究 prompt，只做了 live service reload + governance 验证，避免再次触发低价值重复提问风险
- 没有改动 pre-existing dirty artifacts
