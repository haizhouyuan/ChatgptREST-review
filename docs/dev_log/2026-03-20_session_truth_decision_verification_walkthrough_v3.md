# 2026-03-20 Session Truth Decision Verification Walkthrough v3

## 1. 任务目标

核验 [2026-03-20_session_truth_decision_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md) 是否已经把前两轮留下的 payload owner 问题收干净，并判断它能否作为当前 freeze。

## 2. 这次核验重点

这次我重点复核了 3 件事：

1. `artifacts/advisor_runs/*` 是否已被正确收进 payload truth
2. `advisor_runs` 是否仍被正确限制在 payload store，而不是 session ledger
3. `repo-local artifact payload truth` 这句是否与当前 live `ARTIFACTS_DIR` 一致

## 3. 重新核对的对象

- [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L108)
- [advisor_runs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/advisor_runs.py#L791)
- [routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L927)
- [routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L1488)
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1834)
- [config.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/config.py#L61)
- [contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md#L30)
- 当前 `systemctl --user cat chatgptrest-api.service`
- 当前 `artifacts/jobs/*`
- 当前 `artifacts/advisor_runs/*`

## 4. 这次确认成立的部分

我确认 `v3` 这次把 payload owner 收口收对了：

- `artifacts/jobs/*` 仍然承载 job payload
- `artifacts/advisor_runs/*` 也确实承载 advisor/controller run payload

同时我也确认它没有引入新的错误解释：

- `advisor_runs` 没有被误写成第四套 session ledger
- 三层 session truth 主模型没有被破坏

## 5. 这次没有发现什么问题

这次没有发现需要继续升级到 `v4` 的实质性问题。

原因很简单：

- 前两轮真正的争议点只剩 payload owner 范围
- `v3` 已经把这个范围从单一路径修成了当前 live 系统可证实的两条主路径
- 其余主模型在代码和 live 状态里都没有新反证

## 6. 边界说明

这次唯一需要保留的边界说明不是 finding，而是表述边界：

- 对外 contract 仍然应该优先说 `ARTIFACTS_DIR` abstraction
- 对当前 live runtime，`CHATGPTREST_ARTIFACTS_DIR` 的 effective 值确实是 `/vol1/1000/projects/ChatgptREST/artifacts`

因此：

- 在“当前 live 系统”语境下写 `repo-local artifact payload truth` 没问题
- 在更抽象的 contract 语境下，仍应记住它本质上是 `ARTIFACTS_DIR` 下的 payload store

## 7. 最终判断

所以这轮核验的最终判断是：

- `v3` 已经足够稳
- 可以作为 `session_truth_decision` 这一线的当前 freeze
- 下一步直接进入 `telemetry_contract_fix_v1` 是合理的

## 8. 产物

本轮新增：

- [2026-03-20_session_truth_decision_verification_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_v3.md)
- [2026-03-20_session_truth_decision_verification_walkthrough_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_walkthrough_v3.md)

## 9. 测试说明

这轮仍然只是文档与代码证据核验，没有改业务代码，没有跑测试。
