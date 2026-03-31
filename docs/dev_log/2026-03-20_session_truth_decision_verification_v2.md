# 2026-03-20 Session Truth Decision Verification v2

## 1. 核验对象

本次核验针对：

- [2026-03-20_session_truth_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md)
- [2026-03-20_session_truth_decision_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_walkthrough_v2.md)

被核验提交：

- `dc8fe7eec22ef4c6b2044dc2d4dc12dadfbf30db`

## 2. 核验结论

这版 `v2` 比 `v1` 明显更准确，且主模型没有失效。

我确认以下 3 个核心判断成立：

1. Layer A 不应再泛写成字面 `~/.openclaw`
   - 正确 owner 是当前 runtime 的 `OPENCLAW_STATE_DIR`
2. `state/agent_sessions` 仍然是 `/v3/agent/*` 的 facade session truth
3. `state/jobdb.sqlite3` 仍然是 execution correlation truth，而不是 session continuity truth

但这版仍然有 1 个剩余精度问题，因此还不能作为最终 freeze 文档：

- [2026-03-20_session_truth_decision_v2.md#L45](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md#L45)、[2026-03-20_session_truth_decision_v2.md#L193](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md#L193)、[2026-03-20_session_truth_decision_v2.md#L276](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md#L276)、[2026-03-20_session_truth_decision_v2.md#L312](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md#L312) 把 artifact payload truth 冻成了单一的 `artifacts/jobs/*`，这仍然过窄。

## 3. 已核实成立的部分

## 3.1 Layer A 修正成立

[runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L519) 说明当前 systemd 基线固定了：

- `HOME=/home/yuanhaizhou/.home-codex-official`
- `OPENCLAW_STATE_DIR=/home/yuanhaizhou/.home-codex-official/.openclaw`

[verify_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/ops/verify_openclaw_openmind_stack.py#L23) 也确认 runtime 优先读取 `OPENCLAW_STATE_DIR`，仅在缺失时回退到 `Path.home() / ".openclaw"`。

[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L194) 到 [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L288) 证明 OpenClaw runtime 自己生成 session/runtime identity，再把这些字段下传给 `/v3/agent/turn`。

所以 `v2` 把 Layer A 收紧成 `OPENCLAW_STATE_DIR` 驱动的 runtime continuity truth，这个修正是对的。

## 3.2 `/v3/agent/*` facade truth 判断仍然成立

[agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L11) 到 [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L32) 说明 `AgentSessionStore.from_env()` 会把 facade session 持久化到 `state/agent_sessions`。

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968) 到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1667) 则说明：

- `POST /v3/agent/turn`
- `GET /v3/agent/session/{session_id}`
- `GET /v3/agent/session/{session_id}/stream`
- `POST /v3/agent/cancel`

都直接依赖这一层的 session ledger。

本地 live 状态也支持这个判断：

- `state/agent_sessions` 当前有 `3` 个 `.json`
- 同目录有 `3` 个 `.events.jsonl`

## 3.3 `jobdb` 只是 execution correlation truth 的判断仍然成立

[db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L619) 到 [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L790) 说明 `controller_runs`、`controller_work_items`、`controller_checkpoints`、`controller_artifacts` 共同组成 execution ledger。

[engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L299) 到 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L319) 说明 `session_id / account_id / thread_id / agent_id` 是 run 关联 identity，不是 continuity owner。

本地 live 数据继续支持这个判断：

- `controller_runs` 中 `130` 条有 `trace_id`
- 其中只有 `55` 条有非空 `session_id`

这说明 `jobdb` 继续扮演 execution correlation ledger，而不是独立 continuity truth。

## 3.4 `/v2/advisor/*` 没有长出第四套 durable session ledger

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L500) 和 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1622) 只证明 `/v2/advisor/advise` 与 `/v2/advisor/ask` 会接收并透传 `session_id`。

repo 内实际持久化 facade session 的实现仍然只出现在 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968) 和 [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L11)。

所以 `v2` 保留“`/v2/advisor/*` 是 session-aware ingress，但没有自己独立 durable ledger”这个结论，也是成立的。

## 4. 剩余问题

## 4.1 Artifact payload truth 仍然被写窄了

`v2` 的剩余问题不在三层 session truth 本身，而在 payload filesystem truth 的 owner 被写窄成了单一路径：

- [2026-03-20_session_truth_decision_v2.md#L45](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md#L45)
- [2026-03-20_session_truth_decision_v2.md#L196](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md#L196)
- [2026-03-20_session_truth_decision_v2.md#L280](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md#L280)
- [2026-03-20_session_truth_decision_v2.md#L312](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md#L312)

这几处都把 payload owner 冻成 `artifacts/jobs/*`。

但代码和 live 状态都表明，当前至少还有一套活跃的 run-level payload 目录：

- [advisor_runs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/advisor_runs.py#L791) 到 [advisor_runs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/advisor_runs.py#L821) 会把 run payload 写到 `artifacts/advisor_runs/<run_id>/...`
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1834) 到 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1843) 会把 `controller_snapshot.json` 写到这条 run-level 路径

本地 live 文件系统也直接存在这些 payload：

- `artifacts/advisor_runs/1630f8414f1e71e24406ba278828dd2c/request.json`
- `artifacts/advisor_runs/1630f8414f1e71e24406ba278828dd2c/snapshot.json`
- `artifacts/advisor_runs/2dbaba45ebb441a49a3ca781b411c18d/controller_snapshot.json`

因此，`artifacts/jobs/*` 可以代表 job payload truth，但不能覆盖全部当前 live payload truth。

## 4.2 更准确的冻结口径

更稳的写法至少应收敛成下面两种之一：

1. 保守写法：
   - artifact payload truth 在 repo-local filesystem artifacts 下
2. 更具体写法：
   - `artifacts/jobs/*` = job payload truth
   - `artifacts/advisor_runs/*` = advisor/controller run payload truth

无论采用哪种写法，都比“只有 `artifacts/jobs/*` 才是 payload truth”更准确。

## 5. 最终结论

我的最终判断是：

- `dc8fe7e` 这版 `v2` 没有推翻 `v1` 的主模型，这一点你的独立判断是对的
- `v2` 已经成功吸收了 Claude 指出的两处真实精度问题
- 但 `v2` 仍然留下了 1 个新的收口缺口：artifact payload owner 写得太窄

所以这版最合理的定性是：

- **三层 session truth 主结论成立**
- **payload filesystem truth 的方向成立**
- **但 payload owner 还需要再补一轮收口，才能作为最终 freeze**

## 6. 建议

下一步如果继续出 `telemetry_contract_fix_v1`，建议先把这里的 payload owner 口径一并修正，否则 telemetry 层很容易继续把：

- job payload delivery
- advisor/controller snapshot payload

混写成同一条 `artifacts/jobs/*` 信号。
