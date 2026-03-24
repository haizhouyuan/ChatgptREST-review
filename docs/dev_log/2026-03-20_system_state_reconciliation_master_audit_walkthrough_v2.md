# 2026-03-20 System State Reconciliation Master Audit Walkthrough v2

## 这次新增做了什么

- 把追溯窗口从 `2026-03-18` 扩到 `2026-03-07`
- 重新梳理了 `advisor runtime`、`OpenClaw rebuild`、`memory vertical slice`、`dual-DB authority`、`controller/team`、`public agent facade / premium ingress / cc-sessiond` 的历史节点
- 把“今天状态”和“形成今天状态的历史原因”分开写

## v2 比 v1 多解决了什么

v1 回答的是：

- 现在哪些东西在跑
- 哪些数字要勘误
- 当前最重要的结构冲突是什么

v2 补回答的是：

- 这些冲突是从哪几天、哪几条主线逐步长出来的
- 哪些系统虽然今天没成为中心，但其实有连续演化历史，不能误判为偶然拼接

## 这次最关键的新认识

1. `03-07` 到 `03-17` 并不是“混乱开发期”，而是至少 5 条合理主线并行推进期。
2. `OpenClaw` 作为 runtime substrate 的身份很早就成立了，不是最近才被发现。
3. `OpenMind` 作为系统身份一直很清晰，但实现逐渐沉到 `ChatgptREST` 里。
4. 知识层最大的问题从 `03-10` 起就不是“功能缺失”，而是 `authority/path divergence`。
5. `team control plane / cc-sessiond` 是重要实验资产，但一直没有真正取代 `jobdb + controller + OpenClaw runtime` 成为主中心。

## 如何使用这版文档

- 如果只想知道“现在是什么状态”，看 v1。
- 如果要做下一步正式规划，必须同时看 v1 和 v2。

更具体地说：

- v1 是状态底稿
- v2 是历史成因底稿

两者结合后，下一步规划才不会继续建立在错误简化之上。
