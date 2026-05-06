# KB + Planning High-Quality Harness Completion Summary V2

这版 `v2` 用来纠正 `v1` 的一个关键口径误差。

`v1` 正确覆盖了：
- ingress / harness / metadata / feedback wiring
- live gate
- acceptance pack

但没有把 `promotion / groundedness / chain` 的 live 数据面跑实。

本次补完之后，真实完成状态如下。

## 已真实完成

1. 垃圾归档与质检门禁
2. `canonical_question` / `valid_from` live 回填
3. `groundedness_audit` live 增长
4. `active / candidate` live 增长
5. `chain_id` live 回填
6. `visit_cooperation_prep` vertical live gate 维持通过

## 关键 before / after

- `active`: `243 -> 816`
- `candidate`: `538 -> 4312`
- `groundedness_audit`: `335 -> 3445`
- `chain_nonempty`: `0 -> 103259`
- `answer_feedback`: `0 -> 7`

planning:

- `planning_active`: `242 -> 815`
- `planning_candidate`: `538 -> 4312`
- `planning_staged`: `35129 -> 30782`
- `planning_groundedness_nonzero`: `375 -> 2308`

## 关键修正

本轮最大的修正不是再写新的 harness，而是：

1. 用真实 live apply 把 planning bulk promotion 跑起来
2. 把 `build_chains()` 改成可安全 live apply 的 metadata-only 模式

否则链构建会覆盖既有 promotion 语义。

## 还没完成

1. 扩容后的 EvoMap 向量重建
2. 业务 query semantic bridging
3. 让“绿源 / 钛虎 / 来访准备”这类 query 稳定得到非零 EvoMap hit

## 正确结论

这条统一主线现在可以被定义为：

**Phase 2 live data movement complete.**

但不能被定义为：

**全业务 query 语义召回 complete.**
