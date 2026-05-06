# 2026-03-20 Session Truth Decision Verification Walkthrough v2

## 1. 任务目标

核验 [2026-03-20_session_truth_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md) 是否已经把 `v1` 的精度问题收干净，并判断它能否直接作为最终 freeze 文档。

## 2. 这次核验重点

这次我重点复核了 4 件事：

1. Layer A 是否已经从泛化的 `~/.openclaw` 收紧到 `OPENCLAW_STATE_DIR`
2. `state/agent_sessions` 是否仍然是 `/v3/agent/*` facade truth
3. `jobdb` 是否已经被准确收紧成 execution correlation truth
4. payload filesystem truth 是否真的只落在 `artifacts/jobs/*`

## 3. 重新核对的代码对象

- [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L519)
- [verify_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/ops/verify_openclaw_openmind_stack.py#L23)
- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L194)
- [agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L11)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L500)
- [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L619)
- [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L108)
- [advisor_runs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/advisor_runs.py#L791)
- [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1834)

## 4. 重新核对的 live 状态

本轮重新确认了这些 live 事实：

- `state/agent_sessions` 当前有 `3` 个 `.json` 和 `3` 个 `.events.jsonl`
- `state/jobdb.sqlite3` 的 `controller_runs` 中有 `130` 条非空 `trace_id`
- 其中只有 `55` 条非空 `session_id`
- 当前 runtime 基线仍是 `/home/yuanhaizhou/.home-codex-official/.openclaw`
- `artifacts/jobs/*` 里有 `request.json / answer.md / result.json / events.jsonl / run_meta.json`
- `artifacts/advisor_runs/*` 里有 `request.json / snapshot.json / controller_snapshot.json`

## 5. 这次确认成立的部分

我确认 `v2` 吸收了两条真实的精度修正：

1. Layer A 的 owner 现在写成 `OPENCLAW_STATE_DIR` 驱动的 runtime continuity truth
2. `jobdb` 对 artifact 的口径现在写成 correlation/index truth，而不是 payload truth

同时我也确认 `v2` 保住了正确的主模型：

- `state/agent_sessions` 仍然是 `/v3/agent/*` facade session truth
- `/v2/advisor/ask` 和 `/v2/advisor/advise` 仍然只是 session-aware ingress
- 它们没有长出第四套 durable session ledger

## 6. 这次发现的剩余问题

`v2` 唯一还没完全收干净的点，是把 payload filesystem truth 的 owner 冻得太窄了。

文档当前写法是：

- `artifacts/jobs/*` = artifact payload truth

但代码和 live 状态都表明至少还有一套当前活跃 payload：

- `artifacts/advisor_runs/<run_id>/request.json`
- `artifacts/advisor_runs/<run_id>/snapshot.json`
- `artifacts/advisor_runs/<run_id>/controller_snapshot.json`

这说明：

- `artifacts/jobs/*` 覆盖了 job payload
- 但没有覆盖 advisor/controller run payload

## 7. 最终判断

所以这版 `v2` 的最准确定性不是“需要推翻重做”，而是：

- 主模型成立
- 两处关键修正成立
- 但 payload owner 还差最后一轮收口

换句话说：

- `v2` 已经足够证明“三层 session truth 仍然成立”
- 但还不适合直接当最终 freeze 文档

## 8. 产物

本轮新增：

- [2026-03-20_session_truth_decision_verification_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_v2.md)
- [2026-03-20_session_truth_decision_verification_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_walkthrough_v2.md)

## 9. 测试说明

这轮仍然只是文档与代码证据核验，没有改业务代码，没有跑测试。
