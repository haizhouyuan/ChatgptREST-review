# Completion Contract Phase 3 Walkthrough v1

日期：2026-03-30  
范围：canonical answer hardening + monitoring / issues / soak / evidence 对齐 `completion_contract`

## 为什么做这轮

Phase 1/2 已经把 P0/P1 consumer 迁到 `completion_contract`，但还有一批 monitoring / issues / soak / evidence 路径仍可能：

- 把 `status == completed` 误当 research truly final
- 继续直读 `answer.md`
- 在 incident / issue / deliverable 聚合中回退到旧 artifact 语义

这会导致：

- issue suppression 过早
- behavior issue 误把 completed-but-non-final research 当普通短完成
- incident evidence 缺失当前 authoritative answer contract
- soak / cold smoke 继续输出不一致的 finality 判断

## 这轮改了什么

### 1. 加显式 `canonical_answer`

在现有 `completion_contract` 基础上，新增 additive 的 `canonical_answer` 视图：

- `record_version`
- `ready`
- `answer_state`
- `finality_reason`
- `authoritative_answer_path`
- `answer_chars`
- `answer_format`
- `answer_provenance`
- `export_available`
- `widget_export_available`

实现位置：

- `chatgptrest/core/completion_contract.py`
- `chatgptrest/core/job_store.py`
- `chatgptrest/api/schemas.py`
- `chatgptrest/api/routes_jobs.py`

### 2. issue / evidence / deliverable 路径对齐

- `chatgptrest/api/routes_issues.py`
  - clean completion 判定改为 authoritative finality
- `chatgptrest/governance/deliverable_aggregator.py`
  - 聚合时优先读取 authoritative answer path
- `ops/maint_daemon.py`
  - incident pack 现在会带上：
    - `completion_contract`
    - `canonical_answer`
    - authoritative answer artifact
- `chatgptrest/ops_shared/behavior_issues.py`
  - 读取 `result.json` 的 completion contract / canonical answer
  - completed-but-non-final research 也会计入 bad completion / resubmit 检测

### 3. soak / cold client / legacy shell 对齐

- `ops/codex_cold_client_smoke.py`
  - 输出 `answer_state`
  - 输出 `authoritative_answer_path`
  - 输出 `answer_provenance`
  - completed-but-non-final research 不再被当成 success
- `ops/chatgpt_agent_shell_v0.py`
  - authoritative-ready 前继续 wait，不提前返回 completed success

## 测试

这轮定向通过：

- `tests/test_contract_v1.py`
- `tests/test_job_view_progress_fields.py`
- `tests/test_codex_cold_client_smoke.py`
- `tests/test_chatgpt_agent_shell_v0_turn_guard.py`
- `tests/test_issue_ledger_api.py`
- `tests/test_system_optimization.py`
- `tests/test_behavior_issue_detection.py`

另做 `py_compile` 覆盖本轮修改文件，通过。

## 当前收口

到 Phase 3 为止，`completion_contract` / `canonical_answer` 已经不只存在于 runtime core，而是进入：

- P0 主调用链
- P1 内部消费链
- P2 monitoring / issues / soak / evidence

所以当前默认行为已经变成：

- research finality 优先看 `completion_contract.answer_state`
- answer deliverable / evidence 优先看 `canonical_answer` 与 `authoritative_answer_path`

## 还没做的事

这轮没有去做：

- 大爆炸文件拆分
- 新建独立存储表的大对象重构
- 全仓 sweep 所有历史 `status == completed`

下一阶段才做：

1. observation -> final answer reducer 的更硬实现
2. monitoring / issues / soak 的更细 heuristics
3. 少量历史 repair / utility / docs 的旧 artifact 口径清退
