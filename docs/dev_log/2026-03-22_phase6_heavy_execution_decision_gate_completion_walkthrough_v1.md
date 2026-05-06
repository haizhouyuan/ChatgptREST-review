# 2026-03-22 Phase 6 Heavy Execution Decision Gate Completion Walkthrough v1

## 做了什么

这轮没有继续写代码，而是把 `Phase 6` 按计划收成了一个决策阶段。

我重新核对了：

- [cc_native.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_native.py) 的 `dispatch_team`
- [team_control_plane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/team_control_plane.py)
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py) 的 `team_execution`
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py) 的 `/cc-team-*` routes
- [cc_sessiond/client.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/cc_sessiond/client.py)
- team topologies / gates / role catalog 配置

然后把这些资产按：

- 真正 live 的 heavy-execution primitive
- 实验层
- residual asset

三类重新划分。

## 为什么这轮不再继续写实现

因为 `Phase 6` 的计划本来就不是：

- 立即做 Work Orchestrator
- 或重新启动通用 team runtime 大工程

而是：

- 给 heavy execution 一个明确 admission gate

前五阶段已经把主业务场景固定到：

- `planning`
- `research`
- `knowledge runtime`

这三条主线上。

在这个前提下，如果不先做裁决，继续写 execution 平台，只会回到旧问题：

- 想要全
- 想要专
- 中间层越长越多
- 主业务样本反而没有真正验证

## 关键发现

### 1. 现有 team 资产不是假的

这次确认：

- `cc_native.dispatch_team()` 确实是真 team primitive
- `TeamControlPlane` 确实是真 durable team ledger
- controller 的 `team_execution` 确实已经进入 live path

所以不能再把它们当 dead code。

### 2. 但它们也还不是“新中心”

同样明确的是：

- public front door 还没有 first-class heavy execution contract
- canonical scenario packs 还没有任何一个默认走 `team`
- OpenClaw continuity 还没真正成为 team supervision 的主宿主
- mixed-runtime 仍未证明

所以这些资产当前更准确的定位是：

- heavy-execution experimental lane

不是：

- Work Orchestrator 主中心

### 3. `cc-sessiond` 不再具备翻盘资格

这轮再次确认：

- `cc-sessiond` 还是 prompt-doc-path / session-centric
- 它不能成为未来 admission gate 的依据

因此本轮文档里明确把它降级为 residual experimental asset。

## 最后裁决

这轮真正冻结下来的裁决只有一句话：

**现在不扶正 Work Orchestrator。**

保留现有 team/runtime 资产继续做显式 opt-in 实验，但不允许它们越过 front-door object、scenario pack、knowledge runtime 这三条已经做实的主线，反向成为新中心。
