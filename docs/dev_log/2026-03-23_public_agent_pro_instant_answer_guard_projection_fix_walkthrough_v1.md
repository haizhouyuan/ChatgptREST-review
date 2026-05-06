# 2026-03-23 Public Agent Pro Instant Answer Guard Projection Fix Walkthrough v1

## 做了什么

我先核了历史实现，确认问题不是“没有 guard”，而是“guard 没完全投影到 public-agent/controller”：

- `chatgpt_web.ask + pro_extended` 的异常快速短答识别仍在
- worker 仍会把这类结果切到 `needs_followup + ProInstantAnswerNeedsRegenerate`
- worker auto-autofix 仍会提交同会话 `regenerate/refresh`

真正的缺口是 controller：

- `ControllerEngine._reconcile_job_work_item()` 之前只收 `completed / error / canceled`
- 当底层 job 已经是 `needs_followup` 时，controller 仍然保留 `WAITING_EXTERNAL`
- 这让 public-agent session 没法稳定表达“这不是普通运行中，而是需要同会话修复”

## 为什么这样改

我没有新增新 guard，也没有放开任何 low-level 例外。

只补 controller 的状态收口：

- `needs_followup` 外部 job
- 正式变成 `WAITING_HUMAN`
- 明确下发 `same_session_repair`

这样 northbound surface 才和现有 low-level guard 语义一致。

## 回归覆盖

我刻意把验证拆成 3 层：

1. low-level guard 仍在
- `test_completion_guard_routes_suspicious_pro_short_answer_to_regenerate_followup`

2. auto-regenerate 提交仍在
- `test_worker_auto_autofix_submits_regenerate_for_pro_instant_answer`

3. controller/public-agent 投影补齐
- `test_controller_reconciles_pro_instant_answer_regenerate_to_waiting_human`
- `test_public_agent_session_projects_pro_instant_answer_regenerate_as_needs_followup`

另外我还补跑了两条旧路径，确认这次修复没把现有语义带坏：

- `test_agent_turn_controller_waits_for_final_answer`
- `test_agent_turn_translates_attachment_contract_block_to_needs_input`
- `test_agent_turn_research_report_pack_uses_report_lane`

## 结果怎么解读

这次之后，`Pro 秒出低质量答案` 这类状态在系统里的链条变成：

1. low-level job 识别可疑快速答案
2. worker 降级为 `needs_followup + ProInstantAnswerNeedsRegenerate`
3. auto-autofix 提交同会话 regenerate
4. controller 不再假装 `WAITING_EXTERNAL`
5. public-agent session 正式显示 `needs_followup + same_session_repair`

## 没做什么

我没有做任何 live ChatGPT Pro smoke。

原因是当前仓库策略明确禁止：

- Pro trivial/test prompt
- `purpose=smoke/test` 的 Pro 请求

所以这次结论完全来自确定性回归，而不是额外消耗 Pro 运行面的试探。
