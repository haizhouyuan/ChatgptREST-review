# 2026-04-03 Planning Agent 未完成部分全量实施计划 v5

## 1. 本版作用

`v5` 是当前 `planning agent` 剩余工作的执行合同。

它回答 5 个问题：

1. 现在到底已经做成了什么
2. 还没做成的部分有哪些
3. 剩余工作应该按什么顺序实施
4. 每个工作包要改哪些代码、实现什么效果、拿什么验收
5. 什么情况下可以对外宣称“planning 第一阶段已经做成”

本版相对 `v4` 的关键更新：

1. 吸收了 `v29` 主计划后的真实状态，不再把单条 lane 修绿误写成整体完成
2. 把“剩余工作”分成 `P1 第一阶段完成必做` 与 `P2 后续增强`
3. 把每个工作包拆成更细的实施步骤、代码范围、测试集合、红队 gate
4. 补充了真实 runner / evidence 约束，避免文档里能跑、现场却因为入口姿势不一致而失败

## 2. 当前现状冻结

### 2.1 已经可信成立的部分

截至 `v29`，下面这些判断可以视为已成立：

1. `OpenClawBot -> plugin -> /v3/agent/turn -> provider lane` 已能触发真实执行
2. `planning task plane` 已有 phase-1 sidecar 基线：`task_id / checkpoint / task_get / task_list / session_get`
3. `meeting_sedimentation / workforce_planning / implementation_plan` 已有 continuity acceptance pack 通过
4. `project_diagnosis / research_decision / leadership_report / planning_general` 已在 task store、route 与 acceptance/exporter 中有代码级支持
5. `planning reviewed runtime pack + planning-priority context + work memory` 已证明有真实价值
6. `OpenClawBot planning live completion quality gate` 已在真实 provider 执行下绿过一轮，并有证据包
7. `publicagentmcp` 的目标边界已经冻结为 `ask wrapper`，不再继续向“大杂烩总控”膨胀

### 2.2 还没有做成的部分

当前还不能宣称已经做成的关键原因在这里：

1. `planning task plane` 还只是 phase-1 continuity layer，不是完整的 task truth layer
2. `OpenClawBot` 还不是“材料一扔就能稳定 intake / 分类 / 记忆更新”的成熟入口
3. 高频 planning 任务虽然已有部分 task type，但还没有全部跑过真实 OpenClaw acceptance
4. `knowledge` 还缺：freshness / active promotion / acceptance coverage / writeback 闭环
5. Anthropic 式 harness 还没有真正成为 planning 主线的生产工作流
6. EvoMap 还没有进入“每任务复盘 + 周期复盘 + 策略回灌”的可用状态
7. 多端统一任务层还没有做到“飞书发起、深度工作台推进、再回飞书继续”的稳定生产闭环

## 3. 第一阶段完成定义

只有下面 8 条同时成立，第一阶段才算真正完成：

1. 你可以从 `Feishu/OpenClawBot` 发起至少 3 类高频 planning 任务
2. 同一任务可以在 `OpenClawBot` 与 `Codex / Claude Code / Antigravity / tmuxagent` 之间继续推进
3. 任务连续性靠 `task_id + checkpoint`，而不是靠某个旧窗口不关
4. 至少 5 类高频 planning 任务达到“可直接使用”
5. `OpenClawBot` 能稳定接住至少 3 类常见材料
6. planning 知识主线能为这些任务稳定供 context，而不是“文档进库了但热路径打不到”
7. 每个关键里程碑都有自动测试、evidence、红队复核
8. 失败能 fail-closed，不会假装完成

## 4. 剩余工作总排序

### P1. 第一阶段完成必做

1. `W1` OpenClawBot 全量 planning task acceptance 跑通
2. `W2` Task Truth Layer 扩成 planning 主线
3. `W3` OpenClawBot 材料 intake 成型
4. `W4` 高频 planning 任务覆盖到真实日常工作
5. `W5` Planning 知识主线补齐 freshness / promotion / writeback
6. `W6` Policy Layer 成型，但 `publicagentmcp` 保持薄边界

### P2. 第一阶段后增强

7. `W7` Anthropic-style harness 真正进入 planning 主线
8. `W8` EvoMap 进入“任务后进化”工作状态

## 5. W1 OpenClawBot 全量 planning task acceptance 跑通

### 目标效果

不再只证明“某一条 lane 修绿了”，而是证明 `OpenClawBot planning task plane` 已经能覆盖主线 planning task 的入口、查询、继续、branch 与 completion 质量。

### 当前差距

1. `openclaw acceptance pack` 代码已经支持 7 类 scenario，但自动测试只盯住其中 3 类
2. runner 现场对 Python 环境敏感，直接 `python3` 运行会因 `PYTHONPATH` 缺失失败
3. 还缺一个“全量 7 类 + branch”的稳定 evidence 基线

### 代码范围

1. `chatgptrest/eval/openclawbot_planning_task_plane_acceptance.py`
2. `ops/export_openclawbot_planning_task_plane_acceptance_pack.py`
3. `tests/test_openclawbot_planning_task_plane_acceptance.py`
4. 必要时：`tests/test_routes_agent_v3_planning_task_plane.py`

### 实施步骤

1. 把 `openclaw acceptance` 的默认验证范围升级为全部 7 类高频 task
2. 修掉 runner 调用姿势不一致问题，统一 `PYTHONPATH=.` 与 `.venv/bin/python`
3. 生成新的全量 acceptance evidence
4. 新增或升级测试，确保不会退回只验证 3 类
5. 红队复核：不是只测 mock happy path，不是靠放宽 gate 过关

### 验收标准

1. `manifest.counts.scenarios == 7`
2. `passed == 7`
3. `branch_passed == true`
4. 每个 scenario 都有 `scenario_result.json`
5. runner 在标准仓库姿势下可复现

### 测试集合

1. `tests/test_openclawbot_planning_task_plane_acceptance.py`
2. `tests/test_routes_agent_v3_planning_task_plane.py`
3. 必要时重跑 `tests/test_openclaw_dynamic_replay_gate.py` 与 `tests/test_openclaw_cognitive_plugins.py`

## 6. W2 Task Truth Layer 扩成 planning 主线

### 目标效果

把现在的 phase-1 continuity sidecar，扩成真正够用的 planning task truth layer。

### 当前差距

1. 现在已经有 `task_id + checkpoint`，但还偏窄
2. 能继续，不代表已经能支撑全部 planning 高频工作
3. `new / continue / branch` 有文档和部分代码，但还没有覆盖全部高频 task
4. 深度工作台与 OpenClawBot 虽能共享一部分 task 事实，但还没形成稳固主线

### 代码范围

1. `chatgptrest/planning/meeting_task_store.py`
2. `chatgptrest/api/routes_agent_v3.py`
3. `scripts/planning_task_checkpoint_complete.py`
4. `tests/test_meeting_task_store.py`
5. `tests/test_routes_agent_v3_meeting_task_layer.py`
6. `tests/test_routes_agent_v3_planning_task_plane.py`
7. `ops/export_planning_phase1_continuity_acceptance_pack.py`

### 实施步骤

1. 把已存在的 7 类 task type 分成两层：continuity 已完成层、OpenClaw 主线仍需补强层
2. 为 7 类 task 全部补齐：`default checkpoint contract / resume rule / writeback rule / branch rule`
3. 让深度工作台常用完成动作更容易调用，不靠人手拼 payload
4. 让 `task_get / task_list / session_get` 的返回更适合做跨端 handoff
5. 逐类补 acceptance evidence，而不只写单元测试

### 验收标准

1. 至少 7 类 task 全部能创建与继续
2. 至少 5 类 task 全部有 acceptance pack 证明
3. checkpoint 能支持下一端继续，而不是只存聊天摘要
4. `new / continue / branch` 有稳定自动测试覆盖

### 测试集合

1. `tests/test_meeting_task_store.py`
2. `tests/test_routes_agent_v3_meeting_task_layer.py`
3. `tests/test_routes_agent_v3_planning_task_plane.py`
4. `tests/test_planning_task_checkpoint_complete.py`
5. `tests/test_planning_task_checkpoint_writeback.py`
6. `tests/test_export_planning_phase1_continuity_acceptance_pack.py`

## 7. W3 OpenClawBot 材料 intake 成型

### 目标效果

让 `OpenClawBot` 从“能发文字任务”升级成“能稳定接住 planning 常见材料”。

### 当前差距

1. 目前材料能力还是偏窄，主要是文件路径和文本场景
2. 还没形成稳定的 `attachment preflight`
3. 还不能签“微信转发/截图/录音/转写一扔就自动分类并更新记忆”

### 代码范围

1. `OpenClaw/OpenClawBot` ingress / bridge 对应代码
2. `openclaw_extensions/openmind-advisor/`
3. `chatgptrest/api/routes_agent_v3.py`
4. `workspace` / attachment surface
5. intake 相关 eval / smoke / evidence 脚本

### 实施步骤

1. 冻结 `P1` 先支持的材料类型：文本消息、文档/Markdown/CSV/常见附件、会议转写文本
2. 建立 `attachment preflight`：已收到什么、缺什么、缺哪些必须 fail-closed
3. 建立最小 intake 分类：会议沉淀、项目诊断材料、研究判断材料、汇报底稿
4. 决定写回去向：当前 task checkpoint、`handoff`、`decision_ledger`、仅归档不入记忆
5. 对暂不支持的多媒体链路明确返回：不能处理、缺补件、建议下一步

### 验收标准

1. 至少 3 类材料能被稳定 intake
2. 缺件时 fail-closed
3. ingest 结果能进入 task layer 或 memory layer
4. 不再出现“看似接住了其实没进入系统”的假成功

### 测试集合

1. 新增 intake preflight tests
2. OpenClawBot material smoke tests
3. 至少 1 组真实 evidence bundle

## 8. W4 Planning 高频任务覆盖真实日常工作

### 目标效果

不再只围绕样例任务，而是覆盖你 `planning/` 里的真实高频工作。

### 目标任务簇

1. 人员与绩效规划
2. 项目现状诊断
3. 研究到决策稿
4. 汇报材料
5. 会议沉淀
6. 实施计划/任务拆解
7. 风险与优先级梳理

### 当前差距

1. 任务类型虽然已有映射，但 acceptance 还没有覆盖到全部高频工作
2. “可直接使用”的质量门槛还未对每类 task 全部验证

### 代码范围

1. `chatgptrest/planning/meeting_task_store.py`
2. `chatgptrest/api/routes_agent_v3.py`
3. acceptance/export 脚本
4. 相关 tests 与 review docs

### 实施步骤

1. 为每类任务定义：典型入口句式、默认 `task_type`、最小 checkpoint 字段、默认 lane / fast-vs-deep 策略
2. 为每类任务定义 acceptance rubric：不理解偏、不漏项、口径一致、可直接使用、可核验
3. 逐类跑 acceptance pack
4. 红队抽检至少 2 类“看起来像完成但其实不好用”的坏例

### 验收标准

1. 至少 5 类高频任务达到“可直接使用”
2. 每类都有 evidence 与测试，不靠口头判断

## 9. W5 Planning 知识主线补闭环

### 目标效果

让 `planning reviewed runtime pack + work memory` 从“局部好用”变成“稳定为 planning 主线供 context”。

### 当前差距

1. `pack but not runtime-visible` 还存在
2. freshness 与 active promotion 还不足
3. writeback 还没有稳定进入 reviewed active set

### 代码范围

1. `chatgptrest/evomap/knowledge/planning_review_plane.py`
2. `chatgptrest/evomap/knowledge/planning_runtime_pack_search.py`
3. `chatgptrest/cognitive/context_service.py`
4. `chatgptrest/kernel/work_memory_manager.py`
5. 相关 importer / migration / eval

### 实施步骤

1. 盘点关键 planning 文档是否进入 runtime pack
2. 补 fresh pack 更新机制
3. 补 active atom promotion
4. 补 writeback -> reviewed active set
5. 用真实 planning 查询做 live 验证，而不是只看离线库里有没有数据

### 验收标准

1. 关键 planning 查询能稳定命中正确 context
2. `pack but not runtime-visible` 比例显著下降
3. `continue/resume` 时，任务记忆能被真实取回

### 测试集合

1. 相关 knowledge / context / work memory tests
2. 真实 query smoke
3. acceptance evidence

## 10. W6 Policy Layer 成型，但 publicagentmcp 保持薄边界

### 目标效果

减轻 client 使用负担，但不靠继续把 `publicagentmcp` 做胖。

### 当前差距

1. `Lane Policy / Attachment Preflight / Fast vs Deep Delivery` 目前更多还是计划
2. 还没有把这些 policy 真正落到 planning 主线上

### 代码范围

1. planning workflow / skill / policy 文档与执行层
2. `publicagentmcp` 相关边界
3. 客户端默认工作模式说明

### 实施步骤

1. 固化三份 policy：`Lane Policy`、`Attachment Preflight Policy`、`Fast vs Deep Delivery Policy`
2. 把“如何选 lane / 是否后台跑 / 缺附件怎么报”更多上提到 workflow/skill
3. 保持 `publicagentmcp` 只做薄运行时壳：`turn / status / cancel / wait` 与基本附件、后台执行

### 验收标准

1. client 不需要手工理解底层 provider 才能用
2. `publicagentmcp` 不再因“帮 client 擦屁股”继续长胖

## 11. W7 Anthropic-style harness 落地到 planning 主线

### 目标效果

让 planning 主线不只是“能跑”，而是开始具备：planner 扩 spec、generator 按 sprint/contract 实现、evaluator 独立苛刻验收。

### 当前差距

现在还没有形成真正的 production harness 闭环。

### 实施步骤

1. 先选 1 类 planning 高价值任务试点
2. 定义：spec artifact、sprint contract、evaluator rubric
3. 跑多轮反馈与失败回收

### 验收标准

1. 至少 1 类 planning 任务有 harness 试点通过
2. generator 与 evaluator 职责分离
3. evaluator 真能挡住“看似完成”的假完成

## 12. W8 EvoMap 进入任务后进化

### 目标效果

把“每次做完任务都复盘，周期性再复盘”的目标，变成真实工作流。

### 实施步骤

1. 每任务 writeback 时补结构化复盘
2. 定期汇总失败类型、返工模式、常见误判
3. 把结果反哺到 policy、task templates、evaluator rubric

### 验收标准

1. 每任务都有复盘记录
2. 周期复盘能形成下一轮策略更新

## 13. 实施顺序

严格顺序如下：

1. `W1` 全量 OpenClaw acceptance 跑通
2. `W2` Task Truth Layer 扩成 planning 主线
3. `W3` OpenClawBot 材料 intake 成型
4. `W4` 高频 planning 任务覆盖
5. `W5` 知识主线补闭环
6. `W6` policy layer 成型
7. `W7` harness 试点
8. `W8` EvoMap 进化闭环

## 14. 每个工作包的统一 gate

每个工作包完成前都必须同时满足：

1. 代码改动已提交
2. 对应自动测试通过
3. evidence artifact 已生成
4. review 文档和 walkthrough 已落盘
5. 红队复核已完成
6. `gitnexus_detect_changes(scope="staged")` 已检查

## 15. 当前最近一批建议

从现在开始，不再做新的抽象讨论，直接按这个顺序推进：

1. 先把 `W1` 做完：`openclaw acceptance pack` 全量 7 类 + branch、runner 姿势统一、新 evidence bundle
2. 再进入 `W2`：让 7 类 planning task 的 continuity / checkpoint / resume 都变成真实主线

这两包完成后，才能算“planning 第一阶段真的开始进入全量实施”，而不是继续停留在局部修补。
