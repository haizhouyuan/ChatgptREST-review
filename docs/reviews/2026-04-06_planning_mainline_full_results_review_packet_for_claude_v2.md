# 2026-04-06 Planning Mainline Full Results Review Packet For Claude v2

Supersedes:

- `docs/reviews/2026-04-05_planning_mainline_full_results_review_packet_for_claude_v1.md`

## 1. 为什么要出 v2

`v1` 审查包之后，新增了一批非常具体的修复，不在 planning backend 本体，而在
`OpenClaw -> planning` 的插件层：

1. `openmind_advisor_ask` 不再把 `Route / Session / Run / Job` 这种机器元数据顶在答案前面
2. `needs_followup` 不再直接把 `same_session_repair` 这类机器词暴露给用户
3. 对明显的“继续补充/完善/改写”类 follow-up，plugin 现在有安全自动续做兜底

这批修复来自对 `v1` 的进一步评审判断：

> planning backend 的机器合同已经基本可靠，但真正妨碍“正常人用起来顺手”的瓶颈，很大一部分在 OpenClaw 插件层的入口和出口。

## 2. 当前最准确的总判断

我现在的判断比 `v1` 更精确：

> 当前已经做成的是一条“在已证明范围内可直接使用”的 planning 主线，而且围绕它的 OpenClaw 插件入口/出口也更像用户产品了；但仍然没有充分证明真实用户通过正式入口完成了一次真实 planning 工作闭环。

这句话里有两个层次：

1. `planning backend`：
   - 路由、truth、continuity、fail-close、quality gate 都已经具备 phase-1 可用性
2. `OpenClaw plugin layer`：
   - 结果展示更人话
   - 简单 continue 更不容易因为漏传 `taskId` 而断掉

还没有被证明的，是：

3. `正式入口上的真实工作闭环`
   - 即正常用户通过 Feishu/OpenClawBot，把真实 planning 工作做到真正被使用

## 3. 相比 v1 新增的关键结果

### 3.1 OpenClaw 用户先看到答案，不是系统元数据

现在 `openmind_advisor_ask` 的 `content[0].text` 是：

1. 成功时先给答案正文
2. 然后才补充必要的下一步说明
3. 系统元数据继续只保留在 `details`

关键代码：

- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)

关键 review：

- [2026-04-06_openmind_advisor_answer_first_and_safe_continue_execution_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-06_openmind_advisor_answer_first_and_safe_continue_execution_review_v1.md)

### 3.2 fail-close 现在是人话，不是机器语

现在若 backend 收口到 `needs_followup`，plugin 默认呈现的是：

1. 当前结果还不能直接交付
2. 还缺什么
3. 建议下一步怎么补
4. 如果已有草稿，就把草稿一起展示

而不是直接把：

- `same_session_repair`
- `quality_gate_failed`
- `next_action`

这些原始机器概念暴露给用户。

### 3.3 plugin 层新增了安全自动续做兜底

如果调用方没有显式传 `taskId`，但同时满足：

1. 问题明显像“继续补充/完善/改写”
2. 当前 runtime identity 下只看到一个可见 planning task

plugin 现在会自动补：

- `taskId`
- `taskAction=continue`

如果存在多任务歧义，它不会猜。

这意味着：

> 继续做同一件事，不再完全依赖上游 tool-caller 每次都准确传对 `taskId`。

## 4. 当前总效果应该怎么表述

当前更准确的对外表述应是：

1. planning backend 已经是一条相对稳定的 phase-1 工作主链
2. OpenClaw plugin 层的入口/出口现在已经更接近用户产品：
   - 用户先看答案
   - fail-close 看的是人话
   - 简单 follow-up 有安全自动续做
3. 但当前还没有充分证明“正常用户通过正式入口完成真实 planning 工作并真正使用结果”

## 5. 原目标 vs 当前效果（更新版）

| 原目标 | 当前判断 | 备注 |
|---|---|---|
| 正常用户不用懂内部字段 | 基本达到 | 对 planning backend 来说，仍是机器合同；但 OpenClaw plugin 层现在已经明显更像人类入口/出口 |
| 结果不要一上来就是机器信息 | 已达到 | 这是 `v2` 新增明确做到的结果 |
| follow-up 不要太脆弱 | 基本达到 | 简单 continue 已有安全兜底，但复杂 branch 仍依赖上游调用质量 |
| 同一件事能继续做 | 已达到 | backend task plane 已成立；plugin 也补了更安全的单任务自动续接 |
| fail-close 不伪装完成 | 已达到 | backend 与 plugin 层都更清楚 |
| 结果真正被使用 | 仍未充分证明 | 这仍然是当前最大的剩余缺口 |

## 6. 这次新增最值得 Claude 看的文件

代码：

- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- [README.md](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/README.md)

文档：

- [2026-04-06_openmind_advisor_answer_first_and_safe_continue_execution_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-06_openmind_advisor_answer_first_and_safe_continue_execution_review_v1.md)
- [2026-04-06_openmind_advisor_answer_first_and_safe_continue_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-04-06_openmind_advisor_answer_first_and_safe_continue_walkthrough_v1.md)
- [2026-04-06_planning_agent_total_plan_execution_master_v65.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-06_planning_agent_total_plan_execution_master_v65.md)

测试：

- [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py)
- [test_openmind_advisor_truth_surface.py](/vol1/1000/projects/ChatgptREST/tests/test_openmind_advisor_truth_surface.py)
- [test_openclawbot_planning_task_plane_live_completion_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_planning_task_plane_live_completion_gate.py)

## 7. 建议 Claude 重点再审的三个问题

1. 这次 plugin 层修复，是否已经足以支撑“用户不需要先理解内部系统元数据”这条 claim？
2. 安全自动续做的边界是否足够保守，还是仍有误续接风险？
3. 在 plugin 层修复之后，当前还剩下的最大缺口是否已经明确收敛到：
   - 真实使用闭环
   - 真正被使用的产出价值

## 8. 我的更新自评

如果只看 `v1`，我给的是：

- `基本达到预期，但必须带范围限定`

在加上这次 `v2` plugin 修复后，我的自评仍然是：

- `基本达到预期，但离真实使用闭环还差最后一层`

原因是：

1. 现在不只是 backend 管道可用，OpenClaw-facing 出入口也更像产品了
2. 但还没有那份最关键的证据：
   - 一个真实用户通过正式入口，把一个真实 planning 工作做到真的被使用

## 9. 推荐阅读顺序

1. 本文档
2. [2026-04-05_planning_mainline_full_results_review_packet_for_claude_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-05_planning_mainline_full_results_review_packet_for_claude_v1.md)
3. [2026-04-06_openmind_advisor_answer_first_and_safe_continue_execution_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-06_openmind_advisor_answer_first_and_safe_continue_execution_review_v1.md)
4. [2026-04-06_planning_agent_total_plan_execution_master_v65.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-06_planning_agent_total_plan_execution_master_v65.md)
5. [2026-04-05_planning_user_readiness_and_quality_gate_execution_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-05_planning_user_readiness_and_quality_gate_execution_review_v1.md)
6. [2026-04-05_planning_auto_understanding_from_language_and_attachments_execution_review_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-05_planning_auto_understanding_from_language_and_attachments_execution_review_v1.md)
7. [planning_user_readiness_acceptance_pack_20260405_v4/manifest.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/manifest.json)
