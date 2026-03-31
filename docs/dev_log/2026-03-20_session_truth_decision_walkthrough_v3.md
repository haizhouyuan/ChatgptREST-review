# 2026-03-20 Session Truth Decision Walkthrough v3

## 1. 任务目标

在 [2026-03-20_session_truth_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md) 的基础上，结合：

- [2026-03-20_session_truth_decision_verification_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_v2.md)

把 payload owner 的最后一个缺口收口。

这次依然不是顺着核验意见重写架构，而是：

- 保留 `v2` 已经成立的主模型
- 只修复被代码和 live 文件系统钉实的剩余问题

## 2. 这次独立复核的焦点

我这次只重点核一件事：

- artifact payload truth 是否真的只在 `artifacts/jobs/*`

对应要回答的问题是：

1. `advisor_runs` 是不是活跃 payload path
2. 它是 payload store 还是新的 session ledger
3. 修正后是否会影响三层 session truth 主判断

## 3. 这次重新核对的对象

- [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L108)
- [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L243)
- [advisor_runs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/advisor_runs.py#L791)
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1834)
- 当前 `artifacts/jobs/*`
- 当前 `artifacts/advisor_runs/*`

## 4. 这次我接受了什么

我接受了这条剩余精度问题：

- `v2` 把 payload owner 冻成 `artifacts/jobs/*`，范围确实写窄了

因为代码和 live 文件系统都证明：

- `artifacts/jobs/*` 是 job payload truth
- `artifacts/advisor_runs/*` 也是活跃的 run-level payload truth

## 5. 这次我没有接受什么

我没有接受下面这些过度推论：

- “因为有 `artifacts/advisor_runs/*`，所以 `v2` 主模型失效”
- “`advisor_runs` 是第四套 session ledger”
- “payload truth 应该重新并回 `jobdb`”

我的独立判断是：

- 这只是 payload owner 范围问题
- 不是 session truth 架构问题

## 6. `v3` 最终收下来的口径

`v3` 最终冻结成：

1. `OPENCLAW_STATE_DIR`
   - OpenClaw runtime continuity truth
2. `state/agent_sessions`
   - public facade session truth
3. `state/jobdb.sqlite3`
   - execution correlation truth
4. `artifacts/jobs/*`
   - job payload truth
5. `artifacts/advisor_runs/*`
   - advisor/controller run payload truth

如果往上抽象，可以合并表述成：

- **repo-local artifact payload filesystem truth**

## 7. 为什么这版比 `v2` 更稳

因为现在 execution layer 里最容易被继续混写的两个 payload 面都分开了：

- job payload
- advisor/controller snapshot payload

后面做 telemetry、recovery、delivery 验证时，不会再把所有 payload 都假定为 `artifacts/jobs/*`。

## 8. 产物

本轮新增：

- [2026-03-20_session_truth_decision_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md)
- [2026-03-20_session_truth_decision_walkthrough_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_walkthrough_v3.md)

## 9. 测试说明

这次仍然是文档与代码证据校正任务，没有改代码，也没有跑测试。
