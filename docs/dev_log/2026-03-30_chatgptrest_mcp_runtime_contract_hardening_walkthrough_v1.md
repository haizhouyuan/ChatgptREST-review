# 2026-03-30 ChatgptREST MCP Runtime Contract Hardening Walkthrough v1

## 背景

这轮改动只聚焦 ChatgptREST MCP/runtime 在真实研究使用中暴露出来的可用性问题，不做更大的平台重构。目标是把以下三类问题从“靠经验补救”收口到“有明确 contract 的默认行为”：

1. `jobs submit --client-name` 只改 body，不改 header，导致 header/body client identity 分裂。
2. 研究型长任务缺少清晰的 completion contract，stalled + under-min-chars 仍可能被外部误判为完成。
3. 附件预检把 URI-like 文本和 slash-delimited 概念词误判成“本地文件引用”。
4. public agent MCP service identity 漂移到 API allowlist 之外时，只会在首个请求阶段暴露，不会 fail fast。

## 代码改动

### 1. CLI client identity 收敛

提交：

- `4bc9d90` `fix(cli): keep jobs submit client identity in sync`

结果：

- `chatgptrestctl jobs submit --client-name` 现在会统一 body `client.name` 与 `X-Client-Name`。
- 避免 low-level ask guard 收到 header/body 不一致的身份信息。

### 2. 研究型任务 completion contract

提交：

- `9476ca4` `feat(runtime): add research completion contract`

关键文件：

- `chatgptrest/core/completion_contract.py`
- `chatgptrest/worker/worker.py`
- `chatgptrest/core/job_store.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/api/schemas.py`

结果：

- 新增统一 `completion_contract` 视图。
- `deep_research` / `report_grade` / research/report-style ask 不再把 `completion_guard_completed_under_min_chars` 当成最终完成。
- stalled 或 under-min-chars 的研究型答案现在保持非 final，外部可通过 `completion_contract.answer_state` 区分 `partial | provisional | final`。
- `JobView` / `result.json` 现在都能提供同一 completion block，减少客户端对 `answer.md` / `events.jsonl` / `conversation_export` 的猜测。

### 3. 附件预检 false positive 修复

提交：

- `8ae8853` `fix(runtime): avoid slash-like attachment false positives`

关键文件：

- `chatgptrest/core/attachment_contract.py`

结果：

- URI-like 文本（包含 `://`）不再被误判成本地附件。
- slash-delimited 概念词（如 `episodic/semantic/procedural`）不再被误判成本地附件。
- 真正的本地路径仍然会被 `AttachmentContractMissing` fail closed。

### 4. public MCP allowlist drift fail-fast

提交：

- `39e37e3` `fix(mcp): fail fast on allowlist drift`

关键文件：

- `chatgptrest/mcp/agent_mcp.py`

结果：

- public agent MCP 启动时会检查：
  - bearer token 是否存在
  - 当前 MCP service identity 是否在 `CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST`
- 如果 token 已配置但 service identity 未被 allowlist，直接抛 `service_identity_not_allowlisted`，而不是等第一笔 `advisor_agent_turn` 才失败。

## 文档收口

本轮同步更新：

- `docs/contract_v1.md`
- `docs/runbook.md`
- `docs/README.md`

补入了：

- `completion_contract` 对外字段
- 研究型任务 `answer_state=final` 的使用规则
- public MCP runtime allowlist drift fail-fast 行为
- attachment preflight 对 URI-like / slash-delimited 文本的边界

## 验证

本轮定向回归：

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_cli_chatgptrestctl.py \
  tests/test_conversation_export_reconcile.py \
  tests/test_mcp_unified_ask_min_chars.py \
  tests/test_block_smoketest_prefix.py \
  tests/test_jobs_write_guards.py \
  tests/test_min_chars_completion_guard.py \
  tests/test_job_view_progress_fields.py \
  tests/test_contract_v1.py \
  tests/test_worker_and_answer.py \
  tests/test_attachment_contract_preflight.py \
  tests/test_agent_mcp.py
```

以及对应 `py_compile`。

## 对后续维护者的口径

这一轮不要被误读成“ChatgptREST 已经完成大重构”。更准确的口径是：

- 先把 runtime contract 收紧
- 再让文档、状态视图、MCP 行为对齐
- 仍然没有引入更大的对象层或外部消费层改造

如果后续继续做“研究型任务 contract-first 改造”，应在这轮基础上继续推进：

1. 把 `completion_contract` 作为研究型任务唯一外部 finality 视图。
2. 再决定是否需要把 observation/reducer/finality policy 进一步拆文件。
3. 不要回退到让客户端自己猜 `answer.md` / `conversation_export` / `events.jsonl` 哪个更真。
