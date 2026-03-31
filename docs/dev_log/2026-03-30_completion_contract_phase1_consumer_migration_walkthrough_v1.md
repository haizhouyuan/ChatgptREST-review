# Completion Contract Phase 1 Consumer Migration Walkthrough v1

日期：2026-03-30

## Why

这轮不是继续修单个 runtime bug，而是把已经落地的 `completion_contract` 推成系统默认行为。

此前的问题是：

- runtime 已经写出 `completion_contract`
- 但若干 P0 consumer 仍然直接看：
  - `status == "completed"`
  - `answer.md`
  - `conversation_export_path`

结果是：

- 内核说一套
- CLI / MCP / smoke / e2e 又自己猜一套

## What Changed

### 1. Added shared read helpers

文件：

- `chatgptrest/core/completion_contract.py`

新增统一读取入口：

- `completion_contract_from_job_like()`
- `get_completion_answer_state()`
- `is_research_final()`
- `get_authoritative_answer_path()`
- `get_answer_provenance()`

这些 helper 的职责不是重新定义 contract，而是把：

- modern job payload 上已有的 `completion_contract`
- 旧 job / fallback payload 上还能推出来的最小语义

统一成同一套读取面。

### 2. Added machine-readable runtime contract health

文件：

- `chatgptrest/core/runtime_contract.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/api/app.py`
- `chatgptrest/mcp/agent_mcp.py`

新增：

- `GET /health/runtime-contract`
- `GET /v1/health/runtime-contract`

并让 public MCP 启动期 fail-fast 与 health surface 复用同一套 runtime contract state。

### 3. Migrated first-wave P0 consumers

文件：

- `chatgptrest/cli.py`
- `chatgptrest/mcp/server.py`
- `ops/run_convergence_live_matrix.py`
- `ops/antigravity_router_e2e.py`

迁移原则：

- research finality 不再只看 `status == "completed"`
- 统一改成：
  - `completion_contract.answer_state`
  - `authoritative_answer_path`
  - `answer_provenance`

新行为：

- completed 但 `answer_state != final` 的 research 结果，不再直接抓 answer
- MCP/CLI 会显式返回 `await_research_finality`
- live matrix / antigravity e2e 会把这类结果判成 `completed_not_final`，而不是伪装成成功

## Tests

定向新增/更新：

- `tests/test_ops_endpoints.py`
- `tests/test_cli_chatgptrestctl.py`
- `tests/test_mcp_unified_ask_min_chars.py`
- `tests/test_convergence_live_matrix.py`
- `tests/test_antigravity_router_e2e.py`

本轮回归覆盖：

- runtime contract health output
- CLI `jobs run` completed-but-provisional behavior
- MCP result path for completed-but-non-final research
- convergence live matrix classification
- antigravity e2e completed-not-final guard

## Outcome

这轮之后，ChatgptREST 不只是“runtime 产出 completion_contract”，而是：

- 第一批主 consumer 已经开始默认消费它
- allowlist / service identity / contract drift 也有了 machine-readable health

仍未完成的部分：

- P1 consumer 迁移
- observation -> canonical final answer 的进一步显式化
- monitoring / issues / soak 对齐新 contract
