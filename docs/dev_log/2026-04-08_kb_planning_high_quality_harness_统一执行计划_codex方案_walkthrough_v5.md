# KB + Planning High-Quality Harness Walkthrough V5

## 本轮做了什么

1. 接受了“Phase 2 没有 live 跑实”的独立评审。
2. 对 `planning_bulk_groundedness_promotion` 做了多轮 dry-run / live apply。
3. 对 `chain_builder` 做了 live-safe 修补，避免 chain apply 覆盖 promotion 状态。
4. 在 live DB 上真正写入了 chain metadata。

## 关键决策

### 1. 不直接拿旧版 `build_chains()` 写 live

原因：
- 旧语义会把所有有 canonical question 的 atom 重写成 `candidate/superseded`
- 这会破坏已经跑起来的 promotion 结果

处理：
- 新增 `apply_promotion_semantics=False`
- live chain apply 默认只写 metadata

### 2. 先把 DB 面跑实，再谈“完全版”

这轮没有继续扩新任务族、closure 或 detector。
原因是 promotion / chain 的 live 数据面才是更基础的 blocker。

## 关键证据

- [bulk live 1](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T135900Z/summary.json)
- [bulk live 2](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T140337Z/summary.json)
- [bulk live 3](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T140754Z/summary.json)
- [chain live apply](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_chain_backfill/20260408T140142Z/summary.json)

## 结果

最终 DB 聚合：

- `active`: `243 -> 816`
- `candidate`: `538 -> 4312`
- `groundedness_audit`: `335 -> 3445`
- `chain_nonempty`: `0 -> 103259`

## 剩余问题

本轮也确认了另一个事实：

- promotion 解决了“库里有东西但永远 staged”
- 没有解决“业务 query 的公司名/来访词和 atom 形态不匹配”

所以真正剩下的终局问题已经变成：

- 语义召回
- query normalization
- vector 扩容
