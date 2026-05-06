# 2026-04-03 Planning Agent 未完成部分全量实施计划 v1

## 1. 这份计划解决什么

这份计划不是重讲历史，也不是再做一轮口号式规划。

它只回答 4 个问题：

1. 到当前为止，`planning agent` 这条线到底已经完成了什么。
2. 真正还没完成的部分有哪些。
3. 后续应该按什么顺序把这些部分做完。
4. 每一部分做成以后，如何证明“真的达到效果”，而不是又堆一层代码和文档。

## 2. 当前状态冻结

### 2.1 已经站住的部分

当前已经基本成立的，不应再回到“是否要重写”的层面：

1. `planning/` 第一阶段目标已经冻结：
   - 做一个面向 `planning/` 日常工作的长任务 agent
   - 能接任务、读历史、懂现状、持续推进、沉淀记忆
2. surface 分层已经明确：
   - `Feishu` 入口归 `OpenClaw/OpenClawBot`
   - `Codex / Claude Code / Antigravity` 是深度工作台
   - `tmuxagent` 是深度工作台的远程控制面
   - `publicagentmcp` 目标上按 `ask wrapper` 收口
3. `planning task continuity sidecar` 已经有 phase-1 基线：
   - `meeting_sedimentation`
   - `workforce_planning`
   - `implementation_plan`
4. `planning` 知识主线方向已经冻结：
   - `planning review plane`
   - `reviewed runtime pack`
   - `planning-priority context`
   - `active_project / decision_ledger work memory`
5. `OpenClawBot planning task plane` 已经拿到第一批可用证明：
   - continuity proof
   - query surface 摘要化
   - live completion gate 真实 fail-closed

### 2.2 当前还没有完成的部分

下面这些还不能说“已经做成”：

1. `Feishu/OpenClawBot -> planning task plane -> 深度工作台 -> 写回 -> 继续任务`
   这条主链还没有 live 全绿。
2. `OpenClaw dynamic replay harness fetch failed`
   还是当前 live 主阻塞。
3. `task_id + checkpoint + memory writeback`
   目前只是 phase-1 sidecar，不是 final task truth。
4. `Lane Policy / Attachment Preflight / Fast-vs-Deep Delivery`
   还停在文档冻结，没进入真实执行层。
5. `planning runtime pack freshness / promotion / acceptance / writeback`
   还没有补成稳定闭环。
6. `publicagentmcp` 现实代码仍偏厚，和目标边界仍有距离。
7. Anthropic 式 harness 的 planner / evaluator / sprint contract / harsh review
   还没有进入第一阶段生产主链。
8. EvoMap 的“任务后进化”
   还没有成为真实可依赖的工作机制。

## 3. 第一阶段的完成定义

第一阶段不是“做成最终平台”，而是做到下面这句成立：

> 你可以从 `Feishu/OpenClawBot` 发起一类高频 `planning` 任务，系统能稳定生成并维护任务线程，在 `OpenClawBot` 与深度工作台之间持续推进同一个任务，并把阶段结果、待确认项与稳定记忆写回到统一任务真相层；至少 3 类高频任务通过真实验收，且主要 live gate 不再假绿。

要算第一阶段完成，必须同时满足：

1. `OpenClawBot` 主链 live green
2. 统一任务线程最小闭环成立
3. 至少 3 类高频 `planning` 任务能跨端 continue
4. `planning` 知识主线能为这些任务提供真实帮助
5. 至少 1 套 policy layer 已经进入真实执行
6. 代码、测试、evidence、red-team 四者一致

## 4. 实施原则

### 4.1 不再先做大平台，再补效果

后续所有工作必须按：

1. 真实主链
2. 真实任务类型
3. 真实 live 验收

来排优先级。

### 4.2 不再把任务层和知识层混成一条线

后续分两条主线并行推进：

1. `任务层`
   - `OpenClawBot` 任务入口
   - `task_id`
   - `checkpoint`
   - `continue/resume`
   - `policy layer`
2. `知识层`
   - reviewed runtime pack
   - work memory
   - promotion/freshness/writeback
   - planning acceptance coverage

### 4.3 不再靠“文档看起来闭环”代替真实完成

每个里程碑都必须同时产出：

1. 代码
2. 测试
3. live or offline evidence
4. red-team review

## 5. 全量工作分解

## W1. OpenClawBot 主链打通

### 目标效果

让 `Feishu/OpenClawBot` 真正成为第一入口，而不是只是一层弱入口壳。

### 当前状态

已经有：

1. query surfaces
2. continuity sidecar 基线
3. live completion gate fail-closed

未完成的是：

1. live ask bootstrap 仍失败
2. OpenClaw main path 还没全绿
3. 主链材料 intake 还没有稳定覆盖附件/录音/转写/外来文件

### 步骤

#### W1-S1. 拿下 `fetch failed`

做什么：

1. 复现 OpenClaw dynamic replay harness 当前 `fetch failed`
2. 证明问题是在：
   - OpenClaw harness
   - OpenClawBot bridge
   - `18711` API
   - 代理/网络/环境
3. 定位最小修复点
4. 修复并补回归

期望效果：

1. live bootstrap 不再失败
2. completion gate 能跑到真正的 terminal completion

验收：

1. 复现场景有 evidence 包
2. 修复后 live completion gate 由 `ask_failed` 变为 green
3. 红队确认不是假绿

#### W1-S2. 完成 canonical main path smoke

做什么：

1. 用 `OpenClawBot` 主链实际发起 `meeting_sedimentation`
2. 验证：
   - 能建 task
   - 能查 task
   - 能写回 checkpoint
   - 能 retrieve/continue
3. 把 smoke 扩到另两类 phase-1 task

期望效果：

1. `OpenClawBot` 不再只是入口声明，而是能真的推动同一个任务线程

验收：

1. 三类任务都至少跑通 1 条主链
2. evidence 中保留：
   - first response
   - task create
   - explicit continue
   - writeback
   - retrieve

#### W1-S3. 补材料 intake 覆盖

做什么：

1. 明确 `OpenClawBot` 对文本、图片、文件、录音、转写的当前支持面
2. 把 phase-1 所需的材料类型接入主链
3. 对不能稳定支持的类型，做 fail-closed 与人工升级路径

期望效果：

1. 用户把会议相关材料丢到 `OpenClawBot` 后，系统能判断：
   - 收到了什么
   - 缺什么
   - 走哪条处理链

验收：

1. 有材料清单 evidence
2. 缺件时不装作能做
3. 至少会议沉淀类材料链可用

## W2. 统一任务线程从 sidecar 提升到可依赖主线

### 目标效果

把现在的 continuity sidecar 从“证明思路可行”推进到“第一阶段真相层可依赖”。

### 当前状态

已经有：

1. `task_id`
2. `checkpoint`
3. `continue/retrieve`
4. phase-1 三类任务

未完成的是：

1. 还不是 final task truth
2. session boundary 仍偏宽
3. read-refresh 还是 phase-1 设计债

### 步骤

#### W2-S1. 任务真相源模型冻结

做什么：

1. 明确 `task_id`、`session_id`、`checkpoint_version`、`memory_writeback` 的职责边界
2. 冻结 read path、write path、resume path 的 authority
3. 冻结 `new / continue / branch` 的真实执行规则

验收：

1. 代码层与文档层口径一致
2. query surface、writeback、continue 不再各用一套概念

#### W2-S2. 收口 session boundary

做什么：

1. 决定 `/v3/agent/session/{session_id}` 是：
   - plugin-only 收口
   - 还是 server-side 全面收口
2. 补最小兼容方案
3. 更新依赖它的 MCP/status callers 与测试

验收：

1. cross-session 越权读取风险下降
2. 现有 caller 不被误伤
3. 红队确认没有引入新的兼容性假完成

#### W2-S3. 处理 read-refresh phase-2

做什么：

在三种方案里明确拍板并实现一种：

1. 继续保留 guarded stateful read
2. 改成显式 refresh
3. 改成后台 reconcile

验收：

1. 行为语义清楚
2. 读接口不再成为长期设计债盲点
3. 测试和 red-team 对这一点达成一致

## W3. 把 policy layer 从文档变成真实执行层

### 目标效果

不把 `publicagentmcp` 做大，但让 client 负担真实下降。

### 当前状态

当前只有 policy 文档，没有真实执行。

### 步骤

#### W3-S1. Lane Policy 落地

做什么：

1. 定义 planning 任务模式到 lane 的映射
2. 不让 client 直接选具体模型
3. 在 `OpenClawBot` / planning agent workflow 中接入

期望效果：

1. 用户只选“快答/深答/双审/继续任务/收材料”
2. 系统自己决定默认 lane

验收：

1. 至少一条主链真正用上 lane policy
2. 模型/能力选择行为可解释、可测试

#### W3-S2. Attachment Preflight 落地

做什么：

1. 进入任务前先列附件清单
2. 判断关键缺件
3. 对缺件场景 fail-closed 或回补件请求

期望效果：

1. 用户不再因为“系统假装收到了材料”而白跑

验收：

1. 材料型任务必须产生 preflight 记录
2. 缺关键件时不得继续伪完成

#### W3-S3. Fast vs Deep Delivery 落地

做什么：

1. 定义 5 分钟内先交付什么
2. 定义哪些任务要转后台
3. 定义后台结果如何回收

期望效果：

1. 用户不会因为 `Pro` 慢而误判系统失效

验收：

1. 有首答 SLA 样例
2. 有后台交付 evidence

## W4. 让 planning 知识主线进入“可依赖”状态

### 目标效果

把已证明方向正确的知识主线补成可依赖能力，而不是继续停在“有一些效果”。

### 当前状态

当前判断已经较稳：

1. 不该整体重构
2. 应补：
   - freshness
   - promotion
   - acceptance
   - writeback

### 步骤

#### W4-S1. Runtime pack freshness 修复

做什么：

1. 找出 pack 过期与 runtime-visible 缺失的关键材料
2. 建最小 refresh pipeline
3. 让 live planning 主链能拿到最新关键内容

验收：

1. release readiness 不再因 stale pack fail
2. live 查询能命中最近关键 planning 材料

#### W4-S2. Active atom promotion 修复

做什么：

1. 找出 pack 内但未 runtime-visible 的 atoms
2. 明确 promotion gate
3. 对 phase-1 任务相关内容优先激活

验收：

1. 热路径不再因为全是 `staged` 而空跑
2. 至少 phase-1 三类任务相关内容进入 active hot path

#### W4-S3. Acceptance coverage 与 writeback 打通

做什么：

1. 为 planning 查询建立验收集
2. 建立任务输出到 work memory / reviewed pack 的最小写回链

验收：

1. 能证明知识主线在真实 planning 任务里有帮助
2. 稳定信息能进对层，不是全部留在聊天里

## W5. 把 P0 场景从局部 proof 提升到真实验收

### 目标效果

第一阶段不能只在会议沉淀上站住。

至少要把 3 类高频任务跑到真实可用：

1. `meeting_sedimentation`
2. `workforce_planning`
3. `implementation_plan`

随后补到原始 P0 验收的 5 场景：

4. 项目现状诊断
5. 研究到决策稿
6. 汇报材料

### 步骤

#### W5-S1. phase-1 三类任务全量 acceptance pack

做什么：

1. 每类任务建立固定输入包
2. 固定期望输出
3. 固定人工核验表
4. 固定 live/offline evidence 导出

验收：

1. 三类任务都能给出：
   - first response
   - continue
   - writeback
   - retrieve
   - output quality

#### W5-S2. 扩到 5 个 P0 必跑场景

做什么：

1. 把原始 `planning_work_agent_acceptance_checklist_v1` 的 5 个场景转换成真实 acceptance pack
2. 每场景都定义：
   - 输入
   - 输出
   - red lines
   - pass/fail

验收：

1. 5 个场景至少完成一轮真实验收
2. 每个场景都有 evidence 包

## W6. 边界裁剪与技术债处理

### 目标效果

避免第一阶段继续被历史残留复杂度拖慢。

### 步骤

#### W6-S1. PublicAgentMCP 边界裁剪

做什么：

1. 按 `ask wrapper` 目标重审现状
2. 定义 phase-1 允许的最小增量
3. 继续把聪明逻辑上提到 policy/workflow/skill

验收：

1. 没有新的大杂烩增长
2. client 负担下降不是靠再塞参数实现

#### W6-S2. 非 phase-1 面的降噪

做什么：

1. `consult`、旧 wrapper、遗留 surface 明确状态
2. 对 phase-1 不需要的能力做文档降级或维护隔离

验收：

1. 第一阶段主链更清楚
2. 不再因为历史层叠导致入口和责任不清

## W7. 第二阶段预留，不抢第一阶段主线

下面这些不是当前不做，而是不抢第一阶段主线：

1. planner/generator/evaluator 全量 harness
2. aggressive multi-agent 协作
3. EvoMap 任务后自动进化闭环
4. 更大范围的 `planning` 全仓多任务类型覆盖

这些能力必须等 W1-W5 基本站住之后再提速。

## 6. 总体执行顺序

## Phase A. 先把 live 主链打通

对应：

1. W1-S1
2. W1-S2
3. W1-S3

阶段目标：

> `OpenClawBot` 真的能带着材料和任务线程推进一条 planning 主链。

## Phase B. 把任务线程从 sidecar 提升成可依赖层

对应：

1. W2-S1
2. W2-S2
3. W2-S3

阶段目标：

> 任务连续性不再只是“能演示”，而是有稳定边界。

## Phase C. 把 policy 变成真实能力

对应：

1. W3-S1
2. W3-S2
3. W3-S3

阶段目标：

> client 负担真实下降，但 `publicagentmcp` 不继续膨胀。

## Phase D. 把知识主线补成可依赖层

对应：

1. W4-S1
2. W4-S2
3. W4-S3

阶段目标：

> planning 任务能稳定借到历史和当前事实，而不是命中率忽高忽低。

## Phase E. 做 P0 验收

对应：

1. W5-S1
2. W5-S2
3. W6-S1
4. W6-S2

阶段目标：

> 至少能对你说：这 5 类高频 planning 工作，哪些已经达到可用标准，哪些还没有。

## 7. 每个阶段的强制产物

每完成一个阶段，必须同时具备：

1. 代码提交
2. walkthrough
3. 证据包
4. 测试结果
5. red-team review
6. master plan 版本更新

## 8. Red-Team Gate

后续 red-team 不再按“每写一点就跑一次”的方式机械执行，而改成：

1. 每个阶段末至少一次
2. 每个高风险边界变更至少一次
3. live gate 修复后必须一次

red-team 工具：

1. 默认 `codex 5.4-xhigh`
2. `claudegac` credit 恢复后可再补一轮独立审核

## 9. 当前第一优先级

当前不再继续扩 task type，不再继续堆文档，先做：

1. `W1-S1` 拿下 `OpenClaw dynamic replay harness fetch failed`
2. 接着跑 `W1-S2` canonical main path smoke
3. 再做 `W1-S3` 材料 intake 补齐

## 10. 一句话总判断

当前这条线最合理的做法不是再重写一套系统，而是：

> 先把 `OpenClawBot -> planning task plane -> 深度工作台 -> checkpoint -> continue` 这条主链打到 live 可用，再把 policy、知识闭环和 P0 验收逐层补齐；只要这条主链没真正站住，后面的 harness 和进化都不该抢主线。
