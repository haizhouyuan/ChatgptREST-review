# 2026-04-02 Planning Knowledge Gap Closure And Rebuild Decision v1

## 1. 结论先说

基于这轮代码核验、定向 pytest、offline validation、live query smoke 和真实 manifest import，我的判断是：

> `planning` 知识主线当前不该重构，应该按最小闭环原则补齐。

更准确地说：

1. `work memory` 已经证明有真实效果，应继续补 ingress、writeback、checkpoint 接线，不应推倒重来。
2. `planning reviewed runtime pack` 已经能命中真实 planning query，应补 freshness、live acceptance 和 active atom promotion，不应重做主架构。
3. `KB / vector / graph` 应保留为支撑层，不应继续膨胀成 planning 第一主线。

## 2. 为什么现在不该重构

### 2.1 work memory 已经过了“有没有效果”的门槛

这轮真实验证已经证明：

1. `planning/docs/backfill` 的 manifests 能被导入 durable memory。
2. `active_project / decision_ledger` 能被 `ContextResolver` 召回。
3. 命中的 memory 对 prompt 结构有直接影响，不只是后台写库成功。

如果这条线要重构，等于把已经能恢复 `planning` 上下文的主资产推翻，得不偿失。

### 2.2 runtime pack 的问题集中在运维和 gate，不在主结构

这轮已经证明：

1. offline `golden-query` validation 能过。
2. live query 对一部分高价值 planning 查询已经能命中。
3. 失败样例里，很多不是“文档不在 pack 里”，而是“文档已在 pack 中，但 atom 仍停在 `candidate / staged`，或 `groundedness = 0.0`，所以被 runtime gate 挡掉”。

这说明：

> pack 主结构已经成立，问题是 freshness、promotion 和 acceptance coverage 没闭环。

### 2.3 现在重构只会把“问题看起来解决了”，不会让效果更好

当前暴露出来的核心问题都不是“大框架错了”：

1. live pack 太旧
2. live acceptance query 集太窄
3. 一批关键 planning docs 未被提升为 runtime-visible atoms
4. ingress 到 work memory 的自动投影没打通
5. fallback KB 对 planning role 的 scope/source gating 不够强

这些都属于“补闭环”问题，不属于“重写平台”问题。

## 3. 这轮最值得保留的主线

### 3.1 第一主线

最该继续投入的是这条窄主线：

`planning review plane -> reviewed runtime pack -> planning-priority ContextResolver -> active_project / decision_ledger / handoff / post_call_triage`

这是当前最直接服务 `planning` 日常工作的知识线。

### 3.2 第二主线

第二条该继续保留的是 durable work memory：

1. `active_project`
2. `decision_ledger`
3. `handoff`
4. `post_call_triage`

它解决的是跨端、跨时段、跨窗口恢复问题，是后面统一逻辑任务层的真正基础。

### 3.3 支撑层

下面这些要保留，但定位要收紧：

1. `KB FTS`
2. `ArtifactRegistry`
3. `KB writeback`
4. `vector recall`
5. `canonical knowledge graph`

它们是证据层、召回层、存储层，不应再和 planning 主答案面混成一条线。

## 4. 当前最关键的缺口

### 4.1 runtime pack freshness

当前 live pack 年龄已经明显超窗，`release readiness` 直接是 `ready=false`。

这意味着：

1. 不是 pack 无效
2. 是当前 serving pack 已经过期

### 4.2 live acceptance 只验证了“旧四题”，不够

offline 4-query 能过，只能证明结构没坏，不能证明今天 planning 高频 query 真能命中。

下一步必须把 acceptance 从“老 golden queries”升级成“当前 planning 高频真实 query 集”。

### 4.3 active atom promotion 不够

当前已经能确认有一批关键文档：

1. 已经进入 reviewed runtime pack
2. 但还没进入 runtime-visible active set

这类文档最危险，因为它会给人一种“已经被纳入 planning pack”的错觉，但实际 live query 打不到。

### 4.4 ingress 到 work memory 的自动投影缺失

work memory 现在最像“有库、有 recall、有导入”，但还不是“真实工作流里的自动积累系统”。

当前欠缺的是从这些入口向 memory 的稳定投影：

1. 飞书任务
2. 会议录音 / 转写
3. 微信转发材料
4. 长任务 checkpoint
5. planning 成果文档的阶段性 writeback

### 4.5 planning fallback gating 不够

当 `planning pack` 不命中时，系统会退回普通 KB。

这不是错，但当前 gating 还不够强，容易把泛知识内容混入 planning prompt，影响口径纯度。

## 5. 最小补齐路线

如果只允许做最小闭环，而不是再开大盘子，我建议按这个顺序补：

### P0

1. 刷新 `planning reviewed runtime pack`
2. 扩大 live acceptance query 集
3. 对当前 `pack but not runtime-visible` 的关键 planning docs 做 atom promotion / groundedness 修补

### P1

1. 把 `handoff / post_call_triage` 接进真实任务主线
2. 打通飞书 / 材料 intake / checkpoint 到 work memory 的 writeback
3. 给 planning role 的 fallback KB 加强 scope/source gating

### P2

1. 再评估 canonical graph 在 planning 里的长期角色
2. 再决定 signals/observer 是否要进入 planning 主闭环

## 6. 不建议现在做的事

1. 不建议大规模重构 KB / graph / memory 主结构。
2. 不建议继续放大“通用知识平台”叙事，压过 planning 窄主线。
3. 不建议把 graph-edge 推理当成 planning 近期主解。
4. 不建议在 ingress / writeback / promotion 没补齐前，再加更多抽象层。

## 7. 给第二个 reviewer 的核验重点

如果让第二个 reviewer 做独立审核，我建议重点核 5 件事：

1. 我把 `work memory` 说成“已证明真可用”，这个判断是否成立。
2. 我把 `runtime pack` 判成“半健康，应补齐不应重构”，这个判断是否成立。
3. 我把 `KB / vector / graph` 降到支撑层，这个判断是否说轻或说重。
4. 我列出的 `P0/P1` 缺口顺序是否合理。
5. 有没有我忽略的“必须重构”的硬证据。

## 8. 最终判断

一句话冻结：

> `planning` 知识主线已经有真实效果，当前主要矛盾不是“要不要重写”，而是“能不能把 freshness、promotion、acceptance、writeback 这几个闭环补完”。
