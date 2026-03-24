# 2026-03-22 Heavy Execution Decision Gate v1

## 1. 这份文档回答什么

`Phase 6` 的目标不是立刻做 `Work Orchestrator`，而是给“重执行层要不要扶正”一个可执行的裁决标准。

这一版只回答 3 个问题：

1. 当前仓里到底已经有哪些 heavy execution 资产。
2. 这些资产哪些是 live path，哪些只是实验资产。
3. 以今天的代码和前五阶段完成度来看，现在应不应该扶正 `Work Orchestrator / Execution Cabin`。

结论先写在前面：

- **当前结论：NO-GO**
- **允许继续的 only path：保留当前 team/runtime 资产作为受限实验层与显式 opt-in lane**
- **不允许做的事：现在就把它升级成新的系统中心**

## 2. 当前已存在的 heavy execution 资产

### 2.1 已存在且有真实代码落点的资产

1. `CcNativeExecutor.dispatch_team()`
   - 文件：[cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py)
   - 作用：
     - 支持 `TeamSpec`
     - fan-out roles
     - synthesis role
     - 写 team events / scorecard / checkpoints
   - 现状：
     - 是当前最完整的 team execution primitive

2. `TeamControlPlane`
   - 文件：[team_control_plane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/team_control_plane.py)
   - 作用：
     - resolve topology
     - create/list/finalize team runs
     - track role state
     - manage checkpoints
   - 现状：
     - 是当前最像 durable heavy-execution ledger 的东西

3. controller 的 `team_execution` lane
   - 文件：[engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py)
   - 作用：
     - 当 route / executor lane / scenario context 触发 team mode 时
     - 创建 `team_execute` work item
     - 通过 `_run_team_dispatch()` 提交 child team executor
     - 回写 `team_run_id` / checkpoints / digest
   - 现状：
     - 已进入 live controller path
     - 但还不是主流默认 lane

4. advisor team control routes
   - 文件：[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)
   - 作用：
     - `/v2/advisor/cc-dispatch-team`
     - `/v2/advisor/cc-team-topologies`
     - `/v2/advisor/cc-team-runs`
     - `/v2/advisor/cc-team-checkpoints/*`
   - 现状：
     - 提供了 explicit control surface
     - 更像 operator / experimental surface，不是 public front door

5. team policy / scorecard
   - 文件：
     - [team_policy.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/team_policy.py)
     - [team_topologies.yaml](/vol1/1000/projects/ChatgptREST/config/team_topologies.yaml)
     - [codex_subagents.yaml](/vol1/1000/projects/ChatgptREST/config/codex_subagents.yaml)
     - [team_gates.yaml](/vol1/1000/projects/ChatgptREST/config/team_gates.yaml)
   - 作用：
     - topology catalog
     - scorecard-based recommendation
     - role/gate metadata
   - 现状：
     - 已具备策略骨架
     - 但角色 runtime 仍高度单一

### 2.2 已存在但不应被误判为主中心的资产

1. `cc-sessiond`
   - 文件：[client.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_sessiond/client.py)
   - 现状：
     - 仍是 prompt-doc-path / session-centric 的实验执行壳
     - 不能作为未来重执行中心

2. `CcExecutor.dispatch_team()`
   - 文件：[cc_executor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_executor.py)
   - 现状：
     - 本质仍是 `agents_json -> dispatch_headless`
     - 更接近 legacy in-process teammate mode
     - 不代表真正的 orchestration center

## 3. 当前 live path 的真实状态

### 3.1 哪些地方已经真的接上了 team execution

1. controller lane 已支持 `team_execution`
   - `engine.py` 的 `_resolve_execution_kind()` 会在这些情况下进入 team：
     - `stable_context.team`
     - `stable_context.topology_id`
     - route in `{funnel, build_feature}`
     - `executor_lane == "team"`

2. controller team path 最终调用的是 `cc_native.dispatch_team()`
   - `_run_team_dispatch()` 明确从 runtime state 取 `cc_native`
   - 这条 path 会把结果回写到 controller ledger

3. advisor runtime 已经注入：
   - `cc_native`
   - `team_control_plane`
   - `team_policy`
   - `scorecard_store`

### 3.2 哪些地方还没有形成主线

1. public front door 没有 first-class heavy execution contract
   - 当前 canonical object 是 `Task Intake Spec`
   - 但它还没有对应稳定的 `HeavyExecutionSpec / RoleAssignmentSpec`
   - team 仍主要通过 `context.team` / `context.topology_id` / admin routes 进入

2. scenario pack 没有把 heavy execution 作为默认或稳定产品语义
   - 当前 planning / research packs 的 `execution_preference` 全部是 `job`
   - 这意味着前五阶段刻意把主业务场景稳在 job/report/funnel 上
   - heavy execution 还没有拿到任何一个 canonical business scenario 的默认准入

3. OpenClaw 的长期在线与 team supervision 还没真正收进同一条产品主链
   - OpenClaw 是 continuity owner
   - 但当前 team runtime 还没有形成：
     - lane registry
     - low-attention digest
     - blocked escalation
     - checkpoint notify loop

4. team runtime 还不是多 runtime 协作中心
   - 当前 `codex_subagents.yaml` 的角色 runtime 全是 `codex_subagent`
   - 还没有稳定的 `CC + Codex + OpenClaw` 混合 runtime contract

## 4. 独立判断：为什么现在不能扶正

### 4.1 现有资产是“可用实验层”，不是“可扶正中枢”

当前代码已经足够证明：

- team execution 不是空壳
- team checkpoint 不是空壳
- controller 与 advisor runtime 已经能挂 team lane

但这还不等于“现在该做 Work Orchestrator”。

因为真正的 Orchestrator 不是只会：

- fan-out roles
- 记 checkpoint
- 存 team_run_id

它还必须回答：

- 什么请求值得进 heavy execution
- 谁负责 long-running supervision
- 谁负责低盯盘汇总
- 谁在 lane 之间检测 drift / blocked / contradiction
- 谁在真正需要人时再叫人

这些能力，当前仓里还没有收成产品级主链。

### 4.2 当前主业务场景并没有证明“job lane 已经不够”

前五阶段的策略很明确：

- `planning` 已被收成 scenario pack
- `research` 已被收成 scenario pack
- `knowledge runtime` 已经重新平衡

而且这些 pack 全部刻意固定为 `execution_preference=job`。

这说明当前系统的独立判断已经是：

- 先把主业务场景做稳
- 不把 heavy execution 提前塞成默认中心

如果现在再扶正 Work Orchestrator，等于主动推翻刚刚建立的前五阶段边界。

### 4.3 角色配置已经有了，但 runtime 多样性还没成立

当前 topologies / roles / gates 已经存在，但：

- role catalog 基本仍围绕 `codex_subagent`
- 没有稳定的 mixed-runtime routing
- 没有证明 `Claude Code`、`Codex`、`OpenClaw child agent` 的角色分工已经跑顺

也就是说：

- team schema 有了
- team ledger 有了
- mixed-runtime orchestrator 还没有

这离“重执行层扶正”还差一整层。

### 4.4 OpenClaw 的强项还没真正被 team runtime 吸收

OpenClaw 的价值在：

- continuity
- notification
- presence
- low-attention runtime substrate

而当前 team assets 主要还停在 ChatgptREST runtime 内部：

- `cc_native`
- `team_control_plane`
- controller `team_execution`

如果现在扶正 Work Orchestrator，极容易再次做出一个：

- 不真正吃到 OpenClaw runtime 优势
- 但又想替代 OpenClaw supervision 角色

的新中间层。

## 5. Phase 6 准入门槛

只有当下面 6 条至少全部满足，heavy execution 才能从实验层升级成正式系统层。

### Gate A: Scenario Need

至少一个 canonical 场景包要满足：

- `planning` 或 `research` 的真实请求
- 在 `job/report/funnel` 下质量或盯盘成本明显不合格
- 且 heavy execution 能稳定改善结果

没有这个证据，就不允许扶正。

### Gate B: Contract Readiness

必须存在一套显式对象，而不是继续靠 `context.team/topology_id` 暗渡：

- `HeavyExecutionSpec`
- `RoleAssignmentSpec`
- `CheckpointPolicy`
- `SupervisionPolicy`

没有 contract，就只是 runtime trick，不是产品级能力。

### Gate C: Single Dispatch Authority

必须能明确回答：

- 哪一条是唯一 team dispatch authority
- 哪一条是唯一 checkpoint truth
- 哪一条是唯一 artifact correlation path

当前离这个目标更近的是：

- `cc_native.dispatch_team`
- `TeamControlPlane`
- controller `team_execution`

但还没有形成完整的 front-door-to-runtime 单链。

### Gate D: Low-Attention Supervision

必须具备真正的低盯盘闭环：

- blocked detection
- digest generation
- escalation
- checkpoint notify
- human wake-up only when needed

没有这一条，heavy execution 只是在把复杂度从用户脑中转移到另一个没人盯的系统里。

### Gate E: Mixed Runtime Proof

必须证明至少一套真正的 mixed-runtime role chain 是稳定的，例如：

- strategist = one runtime
- implementer = another runtime
- reviewer = another runtime

并且有：

- success criteria
- failure modes
- artifact correlation

否则 Work Orchestrator 只是在给单 runtime fan-out 包一层新名字。

### Gate F: Ops Ownership

必须明确：

- service/process owner
- durable state path
- restart/recovery procedure
- telemetry contract
- incident playbook

否则它会重演 `cc-sessiond` 的半成品命运。

## 6. 当前裁决

### 6.1 裁决结果

**NO-GO: 不扶正 Work Orchestrator。**

### 6.2 当前允许保留的 heavy execution 范围

允许继续保留并迭代：

- `cc_native.dispatch_team`
- `TeamControlPlane`
- controller `team_execution`
- advisor `/cc-team-*` control surface

但它们的定位只能是：

- operator-only / experimental heavy-execution lane
- explicit opt-in path
- 未来 admission proof surface

### 6.3 当前不允许做的事

1. 不把 `cc-sessiond` 重新包装成未来中心。
2. 不把任何 team route 接成 planning/research 的默认 execution lane。
3. 不先做任意 topology 的通用 agent team 平台。
4. 不先发明新的 daemon/service 来承接“未来 orchestrator”。

## 7. 下一步真正该做什么

`Phase 6` 完成后的正确方向不是“马上开做 Work Orchestrator”，而是：

1. 从现有 `planning / research` 里选一个真实高价值样本，
   证明 job lane 明显不够。
2. 只为这个样本做一条 mixed-runtime prototype role chain。
3. 把 digest / checkpoint notify / blocked escalation 先接到 OpenClaw continuity surface。
4. 用这个 prototype 反推：
   - contract
   - supervision policy
   - admission checklist

只有这一步跑通，才有资格写 `heavy_execution_decision_gate_v2`。

## 8. 最小结论

今天这个仓已经有 enough team assets 去做 **受限实验**，但还没有 enough product proof 去扶正一个新的 `Work Orchestrator` 中心。

所以这轮的正确决定不是“继续搭服务”，而是：

**把 heavy execution 明确定义为 gated experimental lane，直到出现真实场景证明它必须上桌。**
