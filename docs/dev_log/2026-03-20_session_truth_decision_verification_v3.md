# 2026-03-20 Session Truth Decision Verification v3

## 1. 核验对象

本次核验针对：

- [2026-03-20_session_truth_decision_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md)
- [2026-03-20_session_truth_decision_walkthrough_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_walkthrough_v3.md)

被核验提交：

- `048f73a1a692a6a240d0b19c862b20ac15a37c50`

## 2. 核验结论

这次核验没有发现新的实质性问题。

`v3` 已经把前两轮留下的剩余精度问题收干净，当前可以作为这块的 freeze 口径：

- 三层 session truth 保持成立
- payload truth 不再被误写成单一 `artifacts/jobs/*`
- `artifacts/advisor_runs/*` 被正确收进 run-level payload store，而不是第四套 session ledger

## 3. 已核实成立的部分

## 3.1 三层 session truth 主模型仍然成立

[2026-03-20_session_truth_decision_v3.md#L38](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md#L38) 到 [2026-03-20_session_truth_decision_v3.md#L50](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md#L50) 的主结论，与代码和 live 状态一致：

- OpenClaw continuity 仍然在上游 runtime state dir
- `/v3/agent/*` facade session truth 仍然在 `state/agent_sessions`
- execution correlation truth 仍然在 `state/jobdb.sqlite3`

[agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L11) 到 [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L32) 继续证明 facade session ledger 的持久化路径。

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1667) 继续证明 `/v3/agent/*` 的 session/status/stream/cancel 都依赖这层 ledger。

[db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L619) 到 [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L790) 以及 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L299) 到 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L319) 继续证明 `jobdb` 是 execution correlation ledger，而不是 continuity truth。

## 3.2 `artifacts/jobs/*` 与 `artifacts/advisor_runs/*` 的双路径 payload owner 成立

`v3` 这次最关键的修正是成立的。

[artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L108) 到 [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L266) 继续证明 job payload 直接落在 `jobs/<job_id>/...`，包括：

- `request.json`
- `answer.*`
- `conversation.json`
- `result.json`
- `run_meta.json`

[advisor_runs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/advisor_runs.py#L791) 到 [advisor_runs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/advisor_runs.py#L821) 则明确把 advisor/controller run payload 写到 `advisor_runs/<run_id>/...`。

[routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L927) 到 [routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L934) 说明 `request.json` 会写入这条 run-level 路径。

[routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L1488) 到 [routes_advisor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor.py#L1496) 说明 `takeover.json` 也会进入同一条 run-level payload 路径。

[engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1834) 到 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1843) 继续证明 controller 会写 `controller_snapshot.json` 到 `artifacts/advisor_runs/<run_id>/...`。

本地 live 文件系统也直接存在这两类 payload：

- `artifacts/jobs/<job_id>/{request.json,answer.md,result.json,conversation.json,...}`
- `artifacts/advisor_runs/<run_id>/{request.json,snapshot.json,controller_snapshot.json,takeover.json,...}`

## 3.3 `advisor_runs` 没有被误升格成第四套 session ledger

`v3` 在 [2026-03-20_session_truth_decision_v3.md#L56](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md#L56)、[2026-03-20_session_truth_decision_v3.md#L241](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md#L241) 到 [2026-03-20_session_truth_decision_v3.md#L245](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v3.md#L245) 明确把 `advisor_runs` 定性成 payload store 而不是 session truth。

这一定性和代码一致：

- facade session 仍由 [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L11) 管
- `/v2/advisor/ask` 与 `/v2/advisor/advise` 仍只是 session-aware ingress，见 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L500) 和 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1622)

所以 `advisor_runs` 的修正没有引入新的 split-brain 解释。

## 3.4 `repo-local` 这层表述对当前 live runtime 也是成立的

这里需要区分“当前 live runtime”与“抽象契约”两层。

[config.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/config.py#L61) 到 [config.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/config.py#L64) 说明代码层是通过 `CHATGPTREST_ARTIFACTS_DIR` 解析 artifact root。

[contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md#L30) 到 [contract_v1.md](/vol1/1000/projects/ChatgptREST/docs/contract_v1.md#L33) 说明对外契约仍然只承诺“路径在 `ARTIFACTS_DIR` 之下”，而不承诺绝对路径布局。

本地 live systemd drop-in 则进一步确认，当前 effective `CHATGPTREST_ARTIFACTS_DIR` 已被固定到：

- `/vol1/1000/projects/ChatgptREST/artifacts`

所以 `v3` 写“repo-local artifact payload truth”在当前 live runtime 语境下是成立的。

## 4. 最终结论

我的最终判断是：

- `048f73a` 这版 `v3` 没有新的结构性问题
- 它已经把 session truth 与 payload truth 的边界收到了当前足够稳定的状态
- 当前可以把它当成 `session_truth_decision` 这条线的 freeze 文档

唯一需要保留的边界意识是：

- `repo-local` 依赖当前 effective `CHATGPTREST_ARTIFACTS_DIR`
- 如果未来 runtime 切换 artifact root，freeze 口径应继续保留“`ARTIFACTS_DIR` abstraction”，不要再回退成写死某条绝对路径
