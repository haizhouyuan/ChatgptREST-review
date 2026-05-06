# 2026-03-20 Knowledge Authority Decision Walkthrough v2

## 1. 任务目标

在 `authority_matrix` 被核验修正之后，把知识 authority 决策同步升到同一粒度，避免继续沿用 “EvoMap = 单库” 的压缩叙事。

新增产物：

- [2026-03-20_knowledge_authority_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_v2.md)

## 2. 这次为什么必须补 v2

`knowledge_authority_decision_v1` 的大方向没错：

- split-plane 是对的
- EvoMap 做 canonical knowledge 是对的

但它漏掉了一个会持续制造歧义的对象：

- `~/.openmind/evomap/signals.db`

这个库虽然不是 canonical knowledge 主库，但它又确实是 live runtime 里的 EvoMap 组成部分。如果不写进去，后面会继续出现 “EvoMap 到底是一库还是两库” 的争论。

## 3. 新补的关键证据

直接复核到：

- [evomap/paths.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/paths.py#L9) 默认把 runtime EvoMap observer state 指向 `~/.openmind/evomap/signals.db`
- [advisor/runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L278) 用它初始化 `EvoMapObserver`
- 同一个 runtime 文件又在 [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L366) 初始化 repo-local knowledge DB

所以 v2 必须把 EvoMap 拆成：

- `signals plane`
- `knowledge plane`

## 4. 这次的实质修改

v2 没有改掉 v1 的主判断，而是把结构从两层细化成三层：

1. `runtime working plane`
2. `EvoMap signals plane`
3. `EvoMap canonical knowledge plane`

## 5. 结果

这次之后，知识层的口径已经更完整：

- `memory / KB / events`
  - working plane
- `signals.db`
  - runtime observer plane
- `evomap_knowledge.db`
  - canonical knowledge plane

## 6. 产物

本轮新增：

- [2026-03-20_knowledge_authority_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_v2.md)
- [2026-03-20_knowledge_authority_decision_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_knowledge_authority_decision_walkthrough_v2.md)

## 7. 测试与残留

这次仍是文档修订任务，没有代码改动，也没有跑测试。

下一步最该做的是：

1. `routing_authority_decision_v1`
2. `front_door_contract_v1`
3. `session_truth_decision_v1`
4. 然后才是把这些路径 pin 到 env 和配置里
