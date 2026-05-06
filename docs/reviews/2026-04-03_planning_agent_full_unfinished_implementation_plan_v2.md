# 2026-04-03 Planning Agent 未完成部分全量实施计划 v2

## 1. v2 相比 v1 的收紧点

`v2` 不是推翻 `v1`，而是吸收红队和现场核验后，把最关键的执行顺序改对。

这次收紧了 5 个点：

1. 不再把 `P0` 真任务验收放到最后，而是前移为每个阶段的强制 gate。
2. 不再用“结构更清楚、边界更一致”这类过程话术当完成标准，而是绑定到既有的 `planning_work_agent_acceptance_checklist_v1`。
3. 不再把 `publicagentmcp` 写成“已经站住的基座”，只保留“目标姿态已冻结”。
4. 不再把知识线主要押在 `runtime pack`，而是把 `work memory ingress / handoff / writeback` 提到同级优先级。
5. 现场主阻塞口径更新：
   - 旧的 `OpenClaw dynamic replay harness fetch failed` 需要继续保留观察
   - 但当前最新 live evidence 已经推进到 `gemini_web.ask send phase`
   - 真实非绿原因变成 `Gemini upload menu button not found`
   - 同时暴露出 `job status` 与 `session status` 不一致的新问题

## 2. 当前状态冻结

## 2.1 已经站住的方向

下面这些方向可以继续推进，不需要推翻：

1. 第一阶段主线仍然是 `planning/` 日常工作 agent，不是平台化大扩张。
2. `Feishu` 入口仍归 `OpenClaw/OpenClawBot`，不是 ChatgptREST-native 飞书入口。
3. `Codex / Claude Code / Antigravity` 仍是深度工作台。
4. `publicagentmcp` 的目标姿态仍按 `ask wrapper` 收口。
5. `planning` 知识主线仍然是：
   - reviewed runtime pack
   - planning-priority context
   - work memory
6. `continuity sidecar` 仍然是 phase-1 正确方向：
   - `meeting_sedimentation`
   - `workforce_planning`
   - `implementation_plan`

## 2.2 当前已确认完成的部分

当前已经实做并经多轮核验成立的，是：

1. `OpenClawBot planning task plane` 的第一批 query surfaces
2. phase-1 三类 `planning task` continuity 基线
3. `task_get / task_list / session_get` 的摘要化与 cross-session fail-closed
4. `live completion gate` 的 truthful fail-closed
5. `planning` 知识主线的方向判断与效果分层：
   - work memory 更接近真可用
   - runtime pack 半健康但不该整体重构

## 2.3 当前仍未完成的关键能力

下面这些还不能说“已经实现目标效果”：

1. `OpenClawBot -> planning task plane -> 深度工作台 -> checkpoint -> continue`
   还没有 live 全绿。
2. `job -> session -> planning_task checkpoint`
   当前存在状态不一致风险。
3. `Lane Policy / Attachment Preflight / Fast-vs-Deep Delivery`
   还没有真正进入执行链。
4. `work memory ingress / handoff / writeback`
   还没有为 phase-1 主链做成稳定自动投影。
5. `runtime pack freshness / promotion / acceptance`
   还没补成可依赖状态。
6. `publicagentmcp` 现实代码仍偏厚。
7. Anthropic 式 harness 与 EvoMap 进化闭环
   还没有进入第一阶段主线。

## 3. 第一阶段完成定义

第一阶段完成，不等于做成最终平台，而是下面这句成立：

> 你可以从 `OpenClawBot` 发起至少一类高频 `planning` 任务，系统能稳定创建并维护同一个任务线程，支持跨端继续推进，把阶段结果写回统一 checkpoint，并对关键 stable facts 做 work-memory 级写回；同时至少 3 类高频任务通过真实验收，live gate 不再靠假绿或过程解释撑过去。

第一阶段通过，必须同时满足：

1. `OpenClawBot` 主链至少 1 类任务 live green
2. phase-1 三类任务至少都跑通过一次真实 `continue / retrieve / writeback`
3. `job/session/checkpoint` 状态一致性站住
4. `work memory` 已进入至少一条主链
5. 至少 1 套 policy 已进入执行层
6. `planning_work_agent_acceptance_checklist_v1` 的 5 条总通过标准被用于阶段 gate

## 4. 统一验收口径

后续所有阶段都不再各写一套松散“完成定义”，统一使用：

### 4.1 总通过标准

必须对齐：

1. 不理解偏
2. 不漏项
3. 口径一致
4. 可直接使用
5. 可核验

### 4.2 红线

任一阶段只要触碰下面任一条，都不能算通过：

1. 命中错入口或旧口径
2. 状态/边界/数字自相矛盾
3. 把待确认当既成事实
4. 产物不能直接进入工作流
5. live gate 结果依赖解释而非 evidence

### 4.3 阶段 gate 绑定到真实任务

每一阶段都必须绑定至少一个真实任务场景：

1. `meeting_sedimentation`
2. `workforce_planning`
3. `implementation_plan`
4. 后续扩到：
   - 项目现状诊断
   - 研究到决策稿
   - 汇报材料

## 5. 全量工作包

## W1. Live 主链打通

### 目标效果

让 `OpenClawBot` 真正成为一个可用的第一入口，而不是“能发单但主链不可靠”。

### 现场更新后的当前状态

当前 live 非绿已经不是单一 `fetch failed` 口径。

最新现场事实是：

1. OpenClaw plugin 动态调用本身可以成功进入 `/v3/agent/turn`
2. live ask 已能真正落到 `gemini_web.ask`
3. 最新 job evidence 表明 send phase 真实失败点是：
   - `Gemini upload menu button not found`
4. 同时暴露出：
   - `job` 已经 `cooldown/error`
   - 但 `session` 仍然 `running`

所以 W1 现在要同时解决：

1. live provider send 成功率
2. provider 失败时的状态收口真实性

### 步骤

#### W1-S1. live provider blocker 定位与修复

先查并解决当前 live 非绿真实原因：

1. `Gemini upload menu button not found`
2. 若复现回退到 `fetch failed`，继续保留次级排障

验收：

1. 有最小复现证据
2. 修复后 live ask 能至少跑过 send 阶段
3. 红队确认不是换了错误口径

#### W1-S2. `job/session/checkpoint` 一致性修复

做什么：

1. 处理 `job` 已失败但 `session` 仍 running 的不一致
2. 让 live gate 能在 provider 失败时及时、真实、可解释地收口
3. 保证 checkpoint 不会假装完成

验收：

1. provider 失败时 session 会反映真实状态
2. live gate 不再长时间挂在 `running`
3. 失败 evidence 可回指 job/result/events

#### W1-S3. OpenClawBot canonical main path smoke

做什么：

1. 用 `meeting_sedimentation` 跑主链
2. 证明：
   - create
   - continue
   - retrieve
   - checkpoint writeback
3. 跑通后扩到另两类 phase-1 task

验收：

1. 至少 1 类任务 live green
2. 3 类任务都完成一轮 canonical smoke

#### W1-S4. 材料 intake 覆盖

仅在 W1-S1~S3 站住后推进。

做什么：

1. 明确 phase-1 主链支持的材料类型
2. 优先补会议沉淀类需要的材料链
3. 对不稳定材料类型 fail-closed

验收：

1. 有 attachment inventory evidence
2. 缺件时会明确报缺，不伪完成

## W2. 统一任务线程收口

### 目标效果

让 continuity 不只是“能演示”，而是有稳定权责边界。

### 步骤

#### W2-S1. 任务真相模型冻结

冻结：

1. `task_id`
2. `session_id`
3. `checkpoint_version`
4. `memory_writeback`
5. `new / continue / branch`

验收：

1. 同一任务从 OpenClawBot 和深度工作台来回切换，不靠窗口记忆
2. 同一任务的状态变化在 `session/checkpoint` 上一致

#### W2-S2. session boundary 收口

做什么：

1. 决定 `/v3/agent/session/{session_id}` 的边界收口路径
2. 补兼容方案
3. 更新依赖 caller 和测试

验收：

1. cross-session 风险下降
2. 正常 status caller 不被误伤

#### W2-S3. read-refresh phase-2 决策

做什么：

在三种方案中实现一种：

1. guarded stateful read
2. explicit refresh
3. background reconcile

验收：

1. 读接口语义清楚
2. 真实任务 gate 不因 refresh 语义不清而失真

## W3. Policy Layer 执行化

### 目标效果

client 负担下降，但不靠 `publicagentmcp` 继续变胖。

### 步骤

#### W3-S1. Lane Policy

验收：

1. 至少一条真实任务链不需要用户手选具体模型
2. lane 选择能回指 policy

#### W3-S2. Attachment Preflight

验收：

1. 真实材料任务先出附件清单
2. 缺件时 fail-closed 或显式补件请求

#### W3-S3. Fast vs Deep Delivery

验收：

1. 首答和深答边界清楚
2. 至少一个长任务验证“先给 5 分钟首答，再后台深跑”

## W4. 知识主线补齐

### 目标效果

把知识层从“方向对”推进到“可依赖”。

### 子线 A：Work Memory 优先

#### W4-A1. ingress 到 work memory 的真实投影

做什么：

1. `handoff`
2. `post_call_triage`
3. `decision_ledger`
4. `active_project`

进入主链写回。

验收：

1. 至少 phase-1 三类任务里有 work memory evidence
2. 再次 continue 时能借到这些对象

#### W4-A2. work memory 写回治理

验收：

1. 稳定信息进 L1/L2
2. 未确认内容不越级写回

### 子线 B：Runtime Pack 补齐

#### W4-B1. freshness

#### W4-B2. promotion

#### W4-B3. acceptance coverage

这三项继续做，但不再压过 work memory。

验收：

1. pack 不再 stale
2. active atoms 对 phase-1 任务可见
3. live 查询命中提升有 evidence

## W5. P0 真实任务验收

`W5` 不再是最后才做，而是从第一阶段开始贯穿执行。

### W5-S1. phase-1 三类任务持续 gate

每个阶段至少跑：

1. `meeting_sedimentation`
2. `workforce_planning`
3. `implementation_plan`

### W5-S2. 扩到 5 个 P0 场景

在 W1-W4 基本站住后，扩到：

1. 人员规划
2. 项目现状诊断
3. 研究到决策稿
4. 汇报材料
5. 会议沉淀

### W5 的验收纪律

每一轮都必须保留：

1. 输入包
2. 输出包
3. evidence
4. pass/fail
5. red-team verdict

## W6. 边界裁剪与技术债

### W6-S1. `publicagentmcp` 继续向 ask-wrapper-like 边界收

### W6-S2. 非 phase-1 surfaces 降噪

包括但不限于：

1. `consult`
2. legacy wrapper/jobs paths
3. 其他不进入第一阶段主链的旧 surface

## 6. 重新排序后的阶段执行顺序

## Phase A. Live 主链 + 第一个真实任务 gate

对应：

1. W1-S1
2. W1-S2
3. W1-S3
4. W5-S1

阶段目标：

> 至少 1 类真实 planning 任务能从 OpenClawBot 入口 live 走通，并且 provider 失败/成功两侧状态都真实。

## Phase B. 统一任务线程

对应：

1. W2-S1
2. W2-S2
3. W2-S3
4. W5-S1

阶段目标：

> 同一个任务线程的 create/continue/retrieve/writeback 有稳定边界。

## Phase C. Policy 执行化 + 材料链

对应：

1. W3-S1
2. W3-S2
3. W3-S3
4. W1-S4
5. W5-S1

阶段目标：

> client 负担下降，材料任务不再靠经验盲跑。

## Phase D. Work Memory + Runtime Pack 补齐

对应：

1. W4-A1
2. W4-A2
3. W4-B1
4. W4-B2
5. W4-B3
6. W5-S1

阶段目标：

> planning 任务能稳定借到历史和阶段状态，并把稳定结果写回到对的层。

## Phase E. 扩到 5 个 P0 场景 + 边界裁剪

对应：

1. W5-S2
2. W6-S1
3. W6-S2

阶段目标：

> 第一阶段真正能回答：5 类高频 planning 工作，哪些已经可用，哪些仍未达标。

## 7. 每阶段强制产物

每完成一个阶段，必须同时有：

1. 代码提交
2. walkthrough
3. evidence 包
4. 测试结果
5. red-team review
6. master plan 更新
7. 至少 1 个真实任务 gate 结果

## 8. 当前第一优先级

当前最该先做的是：

1. 把 `W1-S1/W1-S2` 做实：
   - 查清 Gemini upload menu blocker
   - 收掉 `job/session` 状态不一致
2. 用 `meeting_sedimentation` 跑出第一个 live green
3. 然后再往其他 task type 扩

## 9. 一句话总判断

现在最合理的做法，不是继续加新类型或新平台层，而是：

> 先把 `OpenClawBot -> live provider -> session/checkpoint truth -> continue` 这条主链做绿，并且每个阶段都绑真实 planning 任务 gate；只有这条线站住了，后面的 policy、知识补齐、P0 全量验收和 Anthropic 式 harness 才不会再次漂移。
