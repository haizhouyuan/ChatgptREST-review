# 2026-03-22 Phase 7 Business Work Sample Validation Completion Walkthrough v2

## 为什么补 v2

`v1` 的问题不是方向错了，而是把验证范围写大了。

我重新回到 [work_sample_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/work_sample_validation.py) 逐步核对后确认：

- 它只重放：
  - intake
  - scenario pack
  - ask contract
  - strategist
- 它没有跑：
  - routes
  - controller
  - context/ingest
  - advisor/report/funnel graph

同时它当前默认样本入口也是：

- `ingress_lane=agent_v3`
- `default_source=rest`

所以 reviewer 指出的两个点都是实话。

## 这轮改了什么

这轮没有改代码，也没有改数据集。

只把 Phase 7 的文档口径收窄成：

- `front-door business-sample semantic validation`

不再写成：

- full-stack business-sample validated

## 为什么我没有去补实现

因为这轮的问题不是实现 bug，而是阶段边界描述不准。

如果现在为了“让文档说大一点也成立”去补：

- OpenClaw ingress 样本
- standard_entry 样本
- consult 样本
- Feishu 样本
- controller/runtime/knowledge 全链样本

那实际上已经是在开新的阶段了，不是修 `Phase 7`。

更干净的处理是：

- 先把 `Phase 7` 的范围说准
- 后面如果要继续扩，再单独做 `Phase 8`

## 最后结论

`Phase 7` 现在的稳定口径是：

- planning/research 的 front-door semantic validation 已完成
- 多入口和 full-stack 样本验证还没做

所以这轮是一次 **scope correction**，不是方向翻盘，也不是实现回退。
