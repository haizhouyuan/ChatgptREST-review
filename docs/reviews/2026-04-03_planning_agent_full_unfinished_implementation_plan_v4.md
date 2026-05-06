# 2026-04-03 Planning Agent 未完成部分全量实施计划 v4

## 1. 本版定位

`v4` 是当前 `planning agent` 未完成部分的全量实施合同。

它不再只描述单一 blocker，而是把从现在到“第一阶段真正做成”之间所有剩余工作，按效果、代码范围、实施步骤、验收标准、测试与红队 gate 全量冻结。

本版口径统一为：

1. `Feishu` 入口必须走 `OpenClaw/OpenClawBot`
2. 深度执行主工作台仍是 `Codex / Claude Code / Antigravity / tmuxagent`
3. `publicagentmcp` 按 `ask wrapper` 收口，不继续长成总控大杂烩
4. `planning` 主线分成两条并行建设线：
   - `任务线`: 从无到有建成真正可继续、可恢复、可回写的 task truth layer
   - `知识线`: 在已有能力上补 freshness / promotion / acceptance / writeback 闭环
5. 所有阶段都必须经过代码测试、evidence 验收、红队复核，不能只靠文档判断

## 2. 当前现状冻结

### 2.1 已经做成的部分

截至本版，已经可信成立的部分是：

1. `OpenClawBot -> plugin -> /v3/agent/turn -> provider lane` 已能触发真实执行
2. `planning task plane` 已有 `task_id / checkpoint / query / session` 的 phase-1 sidecar 基线
3. `meeting_sedimentation / workforce_planning / implementation_plan` 三类窄任务已有 acceptance pack 通过
4. `planning reviewed runtime pack + planning-priority context + work memory` 已证明有真实价值
5. `compact implementation-plan next steps` 的本地 contract、serialization 与 answer normalization 已被代码测试证明
6. `consult` 回归、Gemini wrong-thread 假绿、live gate 假绿，这几类明显 bug 已被收口

### 2.2 还没有做成的部分

仍未完成、且必须进入总实施计划的部分是：

1. `OpenClawBot` 主链 live completion 仍未全绿，前线 blocker 还是 Gemini live thread persistence
2. `phase-1 task truth layer` 还是窄实现，不足以支撑全部 planning 高频工作
3. `OpenClawBot` 还不是“把材料一扔就能稳定 intake / 分类 / 记忆更新”的成熟入口
4. `planning` 高频任务类型还没有全量覆盖到你的真实日常工作
5. `knowledge` 还缺 freshness / promotion / acceptance / writeback 的自动闭环
6. Anthropic 式 harness 还没有真正落成 planning 主线的 planner / generator / evaluator 闭环
7. EvoMap 进化机制还没有进入“每任务复盘 + 周期复盘 + 策略反哺”的工作状态

## 3. 第一阶段完成定义

第一阶段只有在下面 7 条同时成立时，才算真正完成：

1. 你可以从 `Feishu/OpenClawBot` 发起至少一种高频 planning 任务
2. agent 能在 `OpenClawBot` 与深度工作台之间稳定继续同一个任务
3. 任务有真实 `task_id`、可恢复 `checkpoint`、明确 `new/continue/branch` 规则
4. 结果能回写为可继续的 handoff artifact，而不是只留在聊天窗口
5. 至少 3 类高频 planning 任务跑通真实 acceptance
6. knowledge 主线能给这些任务提供有效上下文，而不是“做了 KB 但打不到热路径”
7. 每个里程碑都经由自动测试 + evidence + 红队复核，不靠主观口头判断

## 4. 全量工作包

## W1. OpenClawBot 主链 live completion 全绿

### 目标效果

让 `OpenClawBot -> canonical task plane -> provider completion` 对 planning 主线变成真实可用，而不是“能跑到一半”。

### 主要代码范围

1. `openclaw_extensions/openmind-advisor/`
2. `chatgptrest/api/routes_agent_v3.py`
3. `chatgpt_web_mcp/providers/gemini/ask.py`
4. `chatgpt_web_mcp/providers/gemini/wait.py`
5. `chatgptrest/eval/openclawbot_planning_task_plane_live*_gate.py`
6. 对应 `ops/run_*` runner 与 tests

### 实施步骤

1. 把 live blocker 继续收紧到单一可证实 root cause
2. 修复 requested thread retention / wait completion / same-session repair 这条 provider 现场链
3. 保持 fail-closed，不允许错误线程、错误答案、假 completed
4. 重跑 live gate，直到出现真实 `completed + answer_quality_ok`
5. 把 evidence 固化到新的 artifact 目录和 execution review

### 验收标准

1. live completion gate 至少连续两轮 `ok=true`
2. `terminal_status=completed`
3. `answer_quality_ok=true`
4. 不允许靠放松 gate 或关闭 fail-closed 取得“假绿”

### 测试与证据

1. 相关 pytest 通过
2. live gate 产物完整
3. run_meta / manifest / report 三件套一致
4. 红队必须明确复核“不是靠放水变绿”

## W2. Task Truth Layer 从窄切片扩成 planning 主线

### 目标效果

让任务连续性不再靠窗口记忆，而是靠统一的 `task_id + checkpoint + resume`。

### 主要代码范围

1. `chatgptrest/planning/meeting_task_store.py`
2. `chatgptrest/api/routes_agent_v3.py`
3. `scripts/planning_task_checkpoint_complete.py`
4. `tests/test_meeting_task_store.py`
5. `tests/test_routes_agent_v3_meeting_task_layer.py`

### 实施步骤

1. 继续把 `meeting_sedimentation / workforce_planning / implementation_plan` 做实到 live continuation
2. 扩到剩余 P0 高频任务类型：
   - `project_status_diagnosis`
   - `research_to_decision_memo`
   - `reporting_material`
   - `meeting_ingest_and_followup`
3. 为每类 task 定义：
   - `task_type`
   - `default checkpoint schema`
   - `resume rule`
   - `writeback rule`
4. 落地 `new / continue / branch` 的真实执行逻辑，而不是只有文档定义
5. 让 `OpenClawBot` 和深度工作台都能读写同一 task checkpoint

### 验收标准

1. 至少 5 类高频 planning task 能真实继续
2. 同一任务能跨端恢复，不依赖旧窗口常驻
3. checkpoint 内容足够让下一端继续工作，不只是摘要聊天
4. `new / continue / branch` 判定有自动测试覆盖

### 测试与证据

1. task store / route / writeback pytest 全绿
2. 每类 task 至少一份 acceptance pack
3. 红队抽检至少 2 类 task 的 continuity 真实性

## W3. OpenClawBot 入口从“能发任务”扩到“能接材料”

### 目标效果

让你把微信转发、截图、转写、会议材料、外来文件丢到 `OpenClawBot` 后，系统能先稳定接住，再正确分流，而不是只能发文字。

### 主要代码范围

1. `OpenClaw/OpenClawBot` 对应 ingress/bridge
2. `openclaw_extensions/openmind-advisor/`
3. `chatgptrest/api/routes_agent_v3.py`
4. `workspace` / attachment 相关 surface
5. intake eval / smoke tests

### 实施步骤

1. 明确 `OpenClawBot` 当前支持与不支持的材料类型
2. 建立 `attachment preflight`：
   - 收到什么
   - 缺什么
   - 哪些缺件必须 fail-closed
3. 建立 ingest 分类：
   - 会议沉淀
   - 规划资料
   - 外来参考
   - 待归档材料
4. 建立最小记忆写回：
   - 进入哪个 task
   - 是否写 `handoff`
   - 是否写 `decision_ledger`
5. 对暂不支持的多媒体链路，明确 fail-closed 与人工补件提示

### 验收标准

1. `OpenClawBot` 对至少 3 类材料能稳定 intake
2. 缺件时能明确报缺，不装作已处理
3. ingest 结果能进入 task layer 或 memory layer，而不是丢失

## W4. Planning 高频任务类型全覆盖

### 目标效果

把你真实 `planning/` 高频工作从“只支持几个样例”扩到“覆盖主要日常工作”。

### 覆盖范围

1. 人员与绩效规划
2. 项目现状诊断
3. 研究到决策稿
4. 汇报材料
5. 会议沉淀
6. 实施计划/任务拆解
7. 风险与优先级梳理

### 实施步骤

1. 为每类任务定义统一 intake 模板
2. 为每类任务定义最小 checkpoint 字段
3. 为每类任务定义默认 lane / fast-vs-deep policy
4. 为每类任务定义 acceptance rubric
5. 逐类生成 acceptance pack 并跑真验证

### 验收标准

1. 至少 5 类任务达到“可直接使用”
2. 统一满足 5 条质量口径：
   - 不理解偏
   - 不漏项
   - 口径一致
   - 可直接使用
   - 可核验

## W5. Planning 知识主线补闭环

### 目标效果

让 `planning reviewed runtime pack + work memory` 从“局部好用”变成“稳定能打到热路径”。

### 主要代码范围

1. `chatgptrest/evomap/knowledge/planning_review_plane.py`
2. `chatgptrest/evomap/knowledge/planning_runtime_pack_search.py`
3. `chatgptrest/cognitive/context_service.py`
4. `chatgptrest/kernel/work_memory_manager.py`
5. 相关 migration / importer / eval

### 实施步骤

1. 补 runtime pack freshness
2. 补 active atom promotion
3. 补 acceptance coverage
4. 补 writeback 进入 reviewed active set
5. 对关键 planning 文档建立稳定的 evidence-to-context 路径

### 验收标准

1. 关键 planning 查询在 live runtime 中能稳定命中正确 context
2. `pack but not runtime-visible` 文档比例显著下降
3. 工作记忆能真实帮助 continue/resume，而不是只存不取

## W6. Policy Layer 成型，但不把 publicagentmcp 做胖

### 目标效果

减轻 client 负担，但不靠把 `publicagentmcp` 继续做成大杂烩。

### 主要代码范围

1. workflow / skill / policy 文档与执行层
2. `publicagentmcp` 保持薄运行时边界
3. lane / attachment / delivery policies

### 实施步骤

1. 固化 `Lane Policy`
2. 固化 `Attachment Preflight Policy`
3. 固化 `Fast vs Deep Delivery Policy`
4. 明确 client 暴露模式，而不是暴露底层模型细节
5. 把“智能决策”更多放到 workflow/skill/prompt，而不是 MCP runtime

### 验收标准

1. client 不必手工理解底层 provider 才能用
2. `publicagentmcp` 仍保持薄边界
3. 快答/深答/双审/收材料这些模式对用户可理解、可预测

## W7. Harness 与独立验收闭环

### 目标效果

把 Anthropic 式 harness 真正落到 planning 主线上，而不是只停留在研究结论。

### 实施步骤

1. 为 planning 任务落 planner/spec 展开
2. 为高价值任务落 sprint contract / done-definition
3. 引入独立 evaluator，而不是 generator 自评
4. 建立 runtime validation，不只看文字结果
5. 对高风险任务启用 dual review / consult 作为可选 gate

### 验收标准

1. 至少一类 planning 高价值任务跑通 `planner -> execution -> independent review`
2. evaluator 能给出具体失败反馈，而不是空泛 pass/fail
3. acceptance 与实际产物一致，不再靠主观“感觉差不多”

## W8. EvoMap 进化闭环

### 目标效果

让系统不只是完成任务，还能从任务中持续变强。

### 实施步骤

1. 每任务完成后写结构化复盘
2. 周期性汇总 recurring failure / success pattern
3. 把可执行改进写回 policy / checklist / memory
4. 区分任务真相与方法论进化，不把未确认判断直接升格

### 验收标准

1. 至少形成每任务复盘闭环
2. 至少形成一轮周期复盘并反哺策略
3. 复盘结果对后续任务质量有可见改进证据

## 5. 实施顺序

严格按下面顺序推进：

1. `W1` 先把 OpenClawBot live completion 打绿
2. `W2 + W3` 让任务连续性和材料入口能承接真实工作
3. `W4 + W5` 扩真实任务覆盖，并把 knowledge 补齐成可用底盘
4. `W6` 固化 policy，减轻 client 负担但不让 MCP 长胖
5. `W7` 把 harness 真正落到 planning 主线
6. `W8` 再做 EvoMap 进化闭环

## 6. 每个工作包的共同 gate

任何工作包只有同时满足下面 5 条，才算完成：

1. 代码改动已提交
2. 对应 pytest / integration tests 已通过
3. 真实 evidence 已落盘
4. 红队给出 `approve` 或 `approve-with-fixes` 且 blocker 已处理
5. 文档与 walkthrough 已同步

## 7. 最终交付定义

只有在下面 4 件事都成立后，才能向你汇报“第一阶段完成”：

1. `OpenClawBot` 已成为 planning 主入口之一，并能稳定承接真实任务
2. 深度工作台与 OpenClawBot 之间能共享任务真相层
3. 至少 5 类 planning 高频任务达到可直接使用
4. knowledge / policy / evaluator / redteam 全部进入稳定闭环

## 8. 一句话结论

> `v4` 的口径是：从现在到第一阶段真正做成，还剩一整套可枚举、可编码、可测试、可红队复核的工作；接下来必须按工作包一项项实现，而不是再停留在抽象讨论。
