# 2026-04-02 Planning Checkpoint Schema v1

## 1. 目的

这份文档冻结的是 `planning/` 第一阶段的 checkpoint contract。

它回答的问题是：

> 一个任务在飞书、Codex、Claude Code、Antigravity、tmuxagent 之间切换时，靠什么工件来稳定 handoff。

## 2. 冻结 mouthpiece

对 `planning/` 第一阶段，checkpoint 应被定义为：

> 一个面向跨端 handoff 的紧凑任务快照，而不是聊天记录备份，也不是长期知识库本身。

## 3. checkpoint 的角色

checkpoint 不是：

1. 所有消息的原样存档
2. 所有草稿的堆放目录
3. 长期项目台账的替代物

checkpoint 应该只做 4 件事：

1. 说明当前任务做到哪了
2. 说明哪些事实已经确认
3. 说明哪些问题还没解决
4. 说明下一位接手者该怎么继续

## 4. 和现有代码现实的关系

当前 task runtime 里已经有一些相邻对象：

1. [TASK_CONTEXT.lock.json](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_workspace.py#L52)
2. [TASK_STATE.snapshot.json](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_workspace.py#L76)
3. [PROGRESS_LEDGER.jsonl](/vol1/1000/projects/ChatgptREST/chatgptrest/task_runtime/task_workspace.py#L86)

但这些对象当前分别偏向：

1. frozen context
2. state audit mirror
3. progress event log

它们还不等于面向 `planning` 多端 handoff 的 checkpoint。

所以这里冻结的是一个 **上层工作对象 contract**，不是在说 repo 里今天已经有完整实现。

## 5. checkpoint v1 的最小字段

## 5.1 元信息

这些字段解决“这是哪条线程”：

1. `checkpoint_version`
2. `task_id`
3. `parent_task_id`
4. `task_title`
5. `project_or_topic_ref`
6. `created_at`
7. `updated_at`
8. `last_surface`
9. `last_operator`

## 5.2 当前任务定义

这些字段解决“现在在做什么”：

1. `current_objective`
2. `current_output_target`
3. `audience`
4. `scenario`
5. `stage_label`
6. `current_status`

## 5.3 已确认边界

这些字段解决“哪些东西已经定了”：

1. `confirmed_scope_in`
2. `confirmed_scope_out`
3. `confirmed_constraints`
4. `confirmed_assumptions`
5. `fixed_mouthpiece`

## 5.4 未解决问题

这些字段解决“卡在哪儿”：

1. `open_questions`
2. `missing_inputs`
3. `blocked_reasons`
4. `clarify_needed`

## 5.5 当前产物与证据

这些字段解决“已经产出了什么”：

1. `current_artifact_refs`
2. `canonical_entry_refs`
3. `evidence_refs`
4. `source_material_refs`

## 5.6 当前结论与判断

这些字段解决“目前判断到哪儿了”：

1. `decision_summary`
2. `risk_summary`
3. `current_recommendation`
4. `confidence_level`

## 5.7 下一步动作

这些字段解决“接下来怎么办”：

1. `next_actions`
2. `owner_actions`
3. `waiting_on_user`
4. `target_next_output`

## 5.8 记忆写回候选

这些字段解决“哪些信息值得沉淀”：

1. `memory_writeback_candidates`
2. `memory_writeback_decisions`
3. `sensitivity_flags`

## 6. 建议 schema v1

```json
{
  "checkpoint_version": "planning-checkpoint-v1",
  "task_id": "task_xxx",
  "parent_task_id": null,
  "task_title": "北美镁合金结构件项目阶段诊断",
  "project_or_topic_ref": "PRJ-2026-XXX",
  "created_at": "2026-04-02T10:00:00+08:00",
  "updated_at": "2026-04-02T11:20:00+08:00",
  "last_surface": "codex",
  "last_operator": "yuanhaizhou",
  "current_objective": "完成当前阶段诊断与下一步推进建议",
  "current_output_target": "内部工作稿",
  "audience": "自己/团队",
  "scenario": "planning",
  "stage_label": "diagnosis",
  "current_status": "in_progress",
  "confirmed_scope_in": [
    "项目阶段判断",
    "主要风险",
    "下一步动作"
  ],
  "confirmed_scope_out": [
    "客户正式沟通稿"
  ],
  "confirmed_constraints": [
    "只基于当前 planning 内现有材料"
  ],
  "confirmed_assumptions": [],
  "fixed_mouthpiece": "内部诊断稿，不对外",
  "open_questions": [
    "客户侧最新时间表是否已确认"
  ],
  "missing_inputs": [
    "最新会议纪要"
  ],
  "blocked_reasons": [],
  "clarify_needed": false,
  "current_artifact_refs": [
    "/abs/path/to/current_draft.md"
  ],
  "canonical_entry_refs": [
    "/abs/path/to/project_entry.md"
  ],
  "evidence_refs": [
    "/abs/path/to/meeting_summary.md"
  ],
  "source_material_refs": [
    "/abs/path/to/transcript.md"
  ],
  "decision_summary": "当前更可能处于样件验证前的导入准备阶段",
  "risk_summary": [
    "时间表不清",
    "责任人未锁定"
  ],
  "current_recommendation": "先补齐阶段证据，再输出正式里程碑表",
  "confidence_level": "medium",
  "next_actions": [
    "补最新会议材料",
    "整理阶段证据",
    "更新里程碑判断"
  ],
  "owner_actions": [
    "用户确认客户侧时间表"
  ],
  "waiting_on_user": false,
  "target_next_output": "阶段诊断稿 v2",
  "memory_writeback_candidates": [
    {
      "type": "project_state_update",
      "summary": "当前阶段判断与风险变化",
      "target_scope": "L2"
    }
  ],
  "memory_writeback_decisions": [],
  "sensitivity_flags": [
    "internal_only"
  ]
}
```

## 7. 何时必须写 checkpoint

第一阶段建议把下面 6 个时间点当成硬触发：

1. **新任务创建时**
   - 生成初始 checkpoint
2. **完成一次实质性澄清后**
   - 更新目标和边界
3. **完成一轮实质性分析或改稿后**
   - 更新结论、风险、next actions
4. **切换 surface 前**
   - 从飞书切到深度工作台
   - 从深度工作台切回飞书
5. **准备停手让下次继续时**
   - 必须写回 handoff
6. **任务进入完成或归档前**
   - 写最终 checkpoint

## 8. 何时只更新 PROGRESS，不更新 checkpoint

下面这些低价值变化，不必每次都改 checkpoint：

1. 小的措辞修改
2. 一次性的模型试探
3. 中间草稿未成型的推演
4. 未确认的随手想法

这些更适合停留在：

1. `L0 session scratch`
2. `PROGRESS_LEDGER.jsonl`

## 9. checkpoint 的质量规则

一个合格的 checkpoint 至少要满足：

1. **别人能看懂**
   - 不依赖旧窗口上下文
2. **别人能接手**
   - 有清晰的 next actions
3. **别人能分辨已确认与未确认**
   - 不把猜测写成事实
4. **别人能找到证据和入口**
   - 有 refs
5. **别人能知道写回了什么记忆**
   - 有 writeback candidates

## 10. 第一阶段最该避免的坏 checkpoint

1. 只写一句“继续上次那个”
2. 把整段聊天记录原封不动塞进去
3. 不区分已确认和待确认
4. 不写 `current_output_target`
5. 不写 `next_actions`
6. 不写证据与入口 refs

## 11. 一句话结论

`planning` 第一阶段的 checkpoint 应该是：

> 一个足够小、但足够能接手的 handoff artifact；它必须让另一个 surface 或另一次会话在不翻旧窗口的情况下继续工作。
