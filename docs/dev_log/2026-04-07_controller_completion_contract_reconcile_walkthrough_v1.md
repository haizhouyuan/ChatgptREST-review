# 2026-04-07 Controller Completion Contract Reconcile Walkthrough v1

## 背景

A1 已经把 `completion_contract` 投射到了 public agent MCP surface，但 controller 侧仍然保留旧语义：

- `job.status == completed`
- 且 `job.answer_path` 存在

就会被 `_reconcile_job_work_item()` 直接收口成 `DELIVERED`。

这会导致一类剩余错位：

- 低层 job/result 已经把答案标成 `provisional`
- public session 也能看到 `answer_state=provisional`
- 但 controller run 自己仍然认为这次外部执行已经完整交付

因此 A2 的目标不是改 northbound contract，而是让 controller 侧与已有 completion contract 语义对齐。

## 实现

### 1. engine 侧新增 completion 视图 helper

在 `chatgptrest/controller/engine.py` 中新增 `_job_completion_view()`：

- 优先读取 `artifacts/jobs/<job_id>/result.json`
- 若 `result.json` 存在，优先使用其中的 `completion_contract` / `canonical_answer`
- 若 `result.json` 缺失或字段不全，再回退到 `job` 自身字段

这样 controller 不需要重复推导 completion 语义，也不会只看 `jobs` 表的旧 shape。

### 2. completed 分支改成 contract-aware

`_reconcile_job_work_item()` 现在分成两条 completed 路径：

- `canonical_ready=true` 且存在 `authoritative_answer_path`
  - 保持 `DELIVERED`
- `status=completed` 但 `canonical_ready=false`
  - 改为 `WAITING_EXTERNAL`
  - `delivery.status=in_progress`
  - `next_action.type=await_job_completion`
  - `delivery.answer=""`，避免 public consumers 在 schema 上遇到“有时有 answer、有时缺 key”的不一致

这样 controller 不再把 provisional completed job 错收口成 delivered。

### 3. authoritative answer 路径统一

当答案可最终交付时，controller 侧的：

- `output.answer_path`
- `delivery.authoritative_answer_path`
- `artifacts[answer].path`

统一改用 authoritative path，而不是盲信 `job.answer_path`。

### 4. 吸收 GAC 红队审核的收口项

基于 `claudegac` 的 fork-resume 审核，这版 A2 又额外吸收了三项小修复：

- 把 `completion_view` 的读取收窄到 `status=completed` 分支，避免非 completed job 的无意义文件 I/O
- provisional delivery 显式写出 `"answer": ""`
- 增加 legacy 回归用例：`result.json` 缺失时，controller 仍能回退到 job row 字段并正常 `DELIVERED`

## 测试

新增两条 focused tests 到 `tests/test_public_agent_pro_regenerate_guard.py`：

1. `test_controller_reconciles_completed_job_with_final_contract_to_delivered`
   - 验证 final contract 仍然正确收口为 `DELIVERED`

2. `test_controller_keeps_completed_job_with_provisional_contract_waiting_external`
   - 先完成 job
   - 再把 `result.json` 人工改写成 `provisional + canonical_ready=false`
   - 验证 controller 仍保持 `WAITING_EXTERNAL`

3. `test_controller_reconciles_completed_legacy_job_without_result_json_to_delivered`
   - 完成 job 后删除 `result.json`
   - 验证 legacy completed job 仍可安全回退并保持 `DELIVERED`

回归执行：

- `./.venv/bin/pytest -q tests/test_public_agent_pro_regenerate_guard.py`
- `./.venv/bin/pytest -q tests/test_agent_v3_routes.py`
- `./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py -k "controller or v3_ask_returns_controller_snapshot"`
- `./.venv/bin/pytest -q tests/test_routes_agent_v3_session_job_alignment.py`

## 风险与边界

`_reconcile_job_work_item()` 的 GitNexus upstream impact 为 `CRITICAL`，因此 A2 有意保持极小范围：

- 不修改 public session projection
- 不改 `server.py`
- 不改 OpenClaw / OpenMind 入口
- 只让 controller reconcile 改为 contract-aware

## 下一步

A2 完成后，public agent MCP 与 controller 的 completion finality 语义就基本对齐。

后续优先级：

1. 完成 A3 稳态修复与剩余 contract-aware 路径
2. 再进入 `scope_project + project_id` 主线
