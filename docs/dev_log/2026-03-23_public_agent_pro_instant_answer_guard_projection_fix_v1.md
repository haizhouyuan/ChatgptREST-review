# 2026-03-23 Public Agent Pro Instant Answer Guard Projection Fix v1

## 背景

`chatgpt_web.ask + pro_extended` 早就有 worker 侧的异常短答 guard：

- 可疑的 Pro 秒出短答会被降级为 `needs_followup`
- `error_type = ProInstantAnswerNeedsRegenerate`
- worker auto-autofix 会继续提交同会话 `regenerate/refresh`

但这条保护之前没有完整投影到 public-agent/controller 路径。问题不在 low-level guard，而在 controller 对外部 job 的状态收口：

- `ControllerEngine._reconcile_job_work_item()` 只处理 `completed / error / canceled`
- 当底层 job 已经被 worker 降级成 `needs_followup + ProInstantAnswerNeedsRegenerate`
- controller 仍停在 `WAITING_EXTERNAL`
- public-agent session 因此无法正式给出 `needs_followup + same_session_repair`

## 这次修复

文件：

- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py)

修复内容：

1. 当外部 job 进入 `needs_followup` 时，controller 不再继续保持 `WAITING_EXTERNAL`
2. controller 会把该状态正式提升成：
   - `controller_status = WAITING_HUMAN`
   - `work_status = WAITING_HUMAN`
3. 同时写入可供 northbound surface 直接消费的下一步动作：
   - `next_action.type = same_session_repair`
   - `next_action.error_type = ProInstantAnswerNeedsRegenerate`
   - `next_action.retry_after_seconds`
4. delivery summary/blockers 也同步切到 `waiting_human`

## 为什么这是正确修复

这次不是新增另一层 guard，而是补齐现有 guard 链的控制面投影：

- worker 继续负责识别异常快速答案并降级
- auto-autofix 继续负责提交 `regenerate/refresh`
- controller/public-agent 现在不再把这类状态藏在 `WAITING_EXTERNAL`

也就是说，系统不再把“已经识别为可疑 Pro 秒答”的状态伪装成普通运行中。

## 验证

本次**没有做任何 ChatGPT Pro smoke/test prompt**。

验证全部采用确定性回归：

```bash
./.venv/bin/pytest -q \
  tests/test_public_agent_pro_regenerate_guard.py::test_controller_reconciles_pro_instant_answer_regenerate_to_waiting_human \
  tests/test_public_agent_pro_regenerate_guard.py::test_public_agent_session_projects_pro_instant_answer_regenerate_as_needs_followup \
  tests/test_worker_and_answer.py::test_completion_guard_routes_suspicious_pro_short_answer_to_regenerate_followup \
  tests/test_worker_auto_autofix_submit.py::test_worker_auto_autofix_submits_regenerate_for_pro_instant_answer \
  tests/test_agent_v3_routes.py::test_agent_turn_controller_waits_for_final_answer \
  tests/test_routes_agent_v3.py::test_agent_turn_translates_attachment_contract_block_to_needs_input \
  tests/test_routes_agent_v3.py::test_agent_turn_research_report_pack_uses_report_lane

python3 -m py_compile \
  chatgptrest/controller/engine.py \
  tests/test_public_agent_pro_regenerate_guard.py
```

结果：

- `completion_guard -> needs_followup_regenerate`：通过
- `needs_followup_regenerate -> repair.autofix`：通过
- `controller WAITING_EXTERNAL -> WAITING_HUMAN`：通过
- `public-agent session -> needs_followup + same_session_repair`：通过
- 既有 `completed` 路径未回归：通过
- 既有 `AttachmentContractMissing -> needs_input` 路径未回归：通过

## 结论

当前可以确认：

- `ProInstantAnswerNeedsRegenerate` 这条低层 guard 仍然有效
- 它现在已经能被 controller/public-agent 正式投影出来
- public-agent 不会再把这类状态继续藏成普通 `WAITING_EXTERNAL`

## 边界

这次修复证明的是：

- `Pro 秒出低质量答案` 的识别/降级/auto-regenerate 提交链仍在
- public-agent/controller 已能正确投影这类状态

这次**不证明**：

- live ChatGPT Pro provider 长时间稳定性
- full-stack external provider completion proof
- 任何新的 Pro smoke/test 结论
