# 2026-03-20 Session Truth Decision v3

## 1. 决策目标

这份文档承接：

- [2026-03-20_session_truth_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md)
- [2026-03-20_session_truth_decision_verification_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_v2.md)

`v2` 的主模型已经对了，这次不再改三层 session truth，只补最后一处 payload owner 收口：

- `artifact payload truth` 不能只写成 `artifacts/jobs/*`
- 当前 live 系统里还存在活跃的 `artifacts/advisor_runs/*`

## 2. 独立判断

我这次重新回到了代码和 live 文件系统核对，结论是：

- `v2` 对 Layer A、facade session、execution correlation 的判断都成立
- 但 payload owner 仍然写窄了

所以正确修法不是：

- 推翻 `v2`
- 把 payload truth 并入 `jobdb`
- 或把 `advisor_runs` 解释成第四套 session ledger

而是：

- **保留三层 session truth**
- **把 payload owner 收敛成 repo-local artifact payload truth**
- **并明确当前至少有两条活跃 payload 路径：`artifacts/jobs/*` 与 `artifacts/advisor_runs/*`**

## 3. 正式结论

当前系统的准确说法是：

1. **OpenClaw runtime continuity truth**
   - owner：`OPENCLAW_STATE_DIR`
   - 当前 live path：
     - `/home/yuanhaizhou/.home-codex-official/.openclaw`
2. **Public agent facade session truth**
   - owner：`state/agent_sessions`
3. **Execution correlation truth**
   - owner：`state/jobdb.sqlite3`
4. **Repo-local artifact payload truth**
   - owner：
     - `artifacts/jobs/*`
     - `artifacts/advisor_runs/*`

所以整体仍然是：

- **三层 session truth**
- **外加一层 repo-local artifact payload filesystem truth**

第 4 条依然不是新的 session ledger。

## 4. 代码现实

## 4.1 Layer A 继续冻结为 `OPENCLAW_STATE_DIR`

这一层沿用 `v2`。

[runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L519)
和 [verify_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/ops/verify_openclaw_openmind_stack.py#L23)
继续说明：

- runtime continuity owner 是 `OPENCLAW_STATE_DIR`
- 当前 systemd 基线固定到 `/home/yuanhaizhou/.home-codex-official/.openclaw`

[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L194)
到 [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L226)
继续说明：

- OpenClaw runtime identity 先生成
- ChatgptREST 再消费它

所以这一层不变：

- **OpenClaw runtime continuity truth**

## 4.2 `state/agent_sessions` 继续是 `/v3/agent/*` 的 facade-local canonical truth

这一层也沿用 `v2`。

[agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L20)
到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1667)
继续证明：

- `state/agent_sessions` 是 `/v3/agent/*` 的 durable facade session store

当前 live 状态也仍然成立：

- `state/agent_sessions` 下有 `3` 个 `.json`
- 和对应 `3` 个 `.events.jsonl`

## 4.3 `jobdb` 继续只负责 execution correlation

这一层同样沿用 `v2`。

[db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L619)
到 [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L790)
以及 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L299)
到 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L319)
继续说明：

- `jobdb` 是 run/job/work-item/checkpoint/artifact index 的 ledger
- 不是 continuity owner
- 也不是 payload bytes owner

当前 live 数据仍然支持：

- `controller_runs` 里 `130` 条非空 `trace_id`
- `55` 条非空 `session_id`

## 4.4 这次真正要修的是 payload owner 范围

`v2` 把 payload truth 单点冻结成了：

- `artifacts/jobs/*`

这个方向对，但范围不够。

[artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L108)
到 [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L243)
仍然说明：

- job-level payload 落在 `artifacts/jobs/<job_id>/...`
- 包括 `request.json`
- `answer.*`
- `result.json`
- `events.jsonl`

但这不是全部。

[advisor_runs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/advisor_runs.py#L791)
到 [advisor_runs.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/advisor_runs.py#L821)
说明：

- advisor run payload 会落在 `artifacts/advisor_runs/<run_id>/...`
- `write_snapshot_json(...)` / `write_run_json(...)` 都直接写这条路径

[engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1834)
到 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L1843)
进一步说明：

- controller 会写 `controller_snapshot.json`
- 它也是 run-level payload
- 同样进入 `artifacts/advisor_runs/<run_id>/...`

当前 live 文件系统也证明这条路径不是 dead code：

- `artifacts/advisor_runs/1630f8414f1e71e24406ba278828dd2c/request.json`
- `artifacts/advisor_runs/1630f8414f1e71e24406ba278828dd2c/snapshot.json`
- `artifacts/advisor_runs/2dbaba45ebb441a49a3ca781b411c18d/controller_snapshot.json`

所以这层的准确口径应冻结成：

- `artifacts/jobs/*` = **job payload truth**
- `artifacts/advisor_runs/*` = **advisor/controller run payload truth**

或者向上抽象成一句：

- **repo-local artifact payload filesystem truth**

## 4.5 `/v2/advisor/*` 仍然没有独立 durable session ledger

这一点继续保持不变。

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L500)
和 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1622)
继续只证明：

- `/v2/advisor/advise`
- `/v2/advisor/ask`

会接收并透传 `session_id`，但不会自己生成 facade-local durable ledger。

## 5. 正式冻结

## 5.1 Session truth owners

### A. OpenClaw runtime continuity truth

当前 owner：

- `OPENCLAW_STATE_DIR`

当前 live path：

- `/home/yuanhaizhou/.home-codex-official/.openclaw`

结论：

- **A1 Canonical**

### B. Public facade session truth

当前 owner：

- `state/agent_sessions`

结论：

- **A1 Canonical for `/v3/agent/*` surface**

### C. Execution correlation truth

当前 owner：

- `state/jobdb.sqlite3`

结论：

- **A1 Canonical for execution correlation**

## 5.2 Payload truth owners

### D1. Job payload truth

当前 owner：

- `artifacts/jobs/*`

结论：

- **A1 Canonical for job payload content**

### D2. Advisor/controller run payload truth

当前 owner：

- `artifacts/advisor_runs/*`

结论：

- **A1 Canonical for advisor/controller run payload content**

注意：

- `D1/D2` 都不是新的 session truth
- 它们是 repo-local payload stores
- 它们和 `jobdb` 的关系是：
  - `jobdb` 负责 correlation/index
  - filesystem 负责 payload content

## 5.3 从现在开始不能再写的话

从现在开始，后续文档不能再写：

- “session truth = 三账本平权”
- “`~/.openclaw` 无条件等于所有 channel continuity truth”
- “jobdb 拥有 artifact payload truth”
- “artifact payload truth 只有 `artifacts/jobs/*`”
- “`advisor_runs` 是第四套 session ledger”

## 5.4 最终判断

当前系统的最准确说法是：

- **`OPENCLAW_STATE_DIR` = OpenClaw runtime continuity truth**
- **`state/agent_sessions` = public facade session truth**
- **`state/jobdb.sqlite3` = execution correlation truth**
- **`artifacts/jobs/*` + `artifacts/advisor_runs/*` = repo-local artifact payload truth**

这仍然不是平权 split-brain 模型。

而是：

- **三层 session truth**
- **外加一层分类型 payload filesystem truth**

## 6. 对后续工作的影响

基于这个 `v3`，后面几件事的边界应固定成：

1. `session recovery`
   - OpenClaw 恢复上游 continuity
   - `/v3/agent/session/*` 恢复 facade session
   - `jobdb` 恢复 execution correlation
2. `artifact recovery`
   - job payload 看 `artifacts/jobs/*`
   - advisor/controller snapshot payload 看 `artifacts/advisor_runs/*`
3. `telemetry`
   - 不能再把 payload delivery 全压成 `artifacts/jobs/*`
   - 要区分 job payload 与 run snapshot payload

## 7. 最小结论

当前系统不是“三套 session truth 打架”，而是：

- **`OPENCLAW_STATE_DIR` = OpenClaw runtime continuity truth**
- **`state/agent_sessions` = public facade session truth**
- **`state/jobdb.sqlite3` = execution correlation truth**
- **`artifacts/jobs/*` + `artifacts/advisor_runs/*` = repo-local artifact payload truth**

这才是继续做 `telemetry_contract_fix_v1` 时应该使用的准确前提。
