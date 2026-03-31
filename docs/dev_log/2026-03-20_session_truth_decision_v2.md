# 2026-03-20 Session Truth Decision v2

## 1. 决策目标

这份文档承接：

- [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md)
- [2026-03-20_session_truth_decision_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_v1.md)

这次不是推翻 `v1`，而是做两处精度修正：

1. 把 Layer A 从字面 `~/.openclaw` 收紧成当前真实的 `OpenClaw runtime state dir / OPENCLAW_STATE_DIR`
2. 把 `jobdb` 对 artifacts 的表述从“artifact truth”收紧成“artifact correlation/index truth”

要保住的主判断不变：

- 当前系统不是“三账本平权”
- 而是一个 **layered truth model**

## 2. 独立判断

我这次独立回到了代码和 live 状态做复核，结论是：

- `v1` 的三层模型是对的，不需要推翻
- 但 Layer A 的措辞确实写宽了
- `jobdb` 对 artifacts 的措辞也确实写强了

所以正确修法不是“改回四账本/平权账本”，而是：

- **保留三层 session truth**
- **单独补一条 artifact payload truth 在文件系统**

## 3. 正式结论

当前系统的正确说法是：

1. **OpenClaw runtime state dir continuity truth**
   - owner：`OPENCLAW_STATE_DIR`
   - 当前 systemd 基线固定为：
     - `/home/yuanhaizhou/.home-codex-official/.openclaw`
2. **Public agent facade session truth**
   - owner：`state/agent_sessions`
3. **Execution correlation truth**
   - owner：`state/jobdb.sqlite3`
4. **Artifact payload truth**
   - owner：`artifacts/jobs/*`

但要注意：

- 第 4 条不是新的 session ledger
- 它只是 execution layer 旁边的 payload store

所以整体仍然是：

- **三层 session truth**
- **外加一层 artifact payload filesystem truth**

## 4. 代码现实

## 4.1 Layer A 不是抽象 `~/.openclaw`，而是 `OPENCLAW_STATE_DIR`

`v1` 把 Layer A 直接写成 `~/.openclaw`，而且扩成了：

- OpenClaw
- Feishu
- DingTalk
- agent runtime continuity truth

这在方向上接近真实系统，但当前证据只能安全冻结到更窄的说法。

[runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L519) 已经明确写死当前 systemd 基线：

- `HOME=/home/yuanhaizhou/.home-codex-official`
- `OPENCLAW_STATE_DIR=/home/yuanhaizhou/.home-codex-official/.openclaw`

[verify_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/ops/verify_openclaw_openmind_stack.py#L23)
也证明运行时默认读取的是：

- `OPENCLAW_STATE_DIR`
- 若未设置才退回 `Path.home() / ".openclaw"`

[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L194)
到 [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L226)
则证明：

- OpenClaw runtime 自己生成 `sessionKey / sessionId / agentAccountId / agentId`
- bridge 再把这些 identity 下传给 ChatgptREST

所以这层应冻结为：

- **OpenClaw runtime state dir continuity truth**

它回答的是：

- OpenClaw-native runtime continuity 是谁
- OpenClaw 上游 session identity 是谁

这次不再把它直接扩写成“Feishu/DingTalk continuity truth”，除非后续另有直接证据补进来。

## 4.2 `state/agent_sessions` 仍然是 `/v3/agent/*` 的 facade-local canonical truth

这一层在 `v1` 里的核心判断保持不变。

[agent_session_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/agent_session_store.py#L20)
已经固定了 `AgentSessionStore.from_env()` 的落盘规则；当前环境就是：

- `state/agent_sessions`

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968)
到 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L1667)
则证明它直接支撑：

- `POST /v3/agent/turn`
- `GET /v3/agent/session/{session_id}`
- `GET /v3/agent/session/{session_id}/stream`
- `POST /v3/agent/cancel`

当前本地状态也仍然成立：

- `state/agent_sessions` 下有 `3` 个 `.json`
- 以及对应 `3` 个 `.events.jsonl`

所以这层继续冻结为：

- **public agent facade session truth**

## 4.3 `jobdb` 是 execution correlation truth，不是 continuity truth

这一层主判断同样不变。

[db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L619)
到 [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L790)
已经说明：

- `controller_runs` 的自然主键是 `run_id`
- 旁边还有 `controller_work_items`
- `controller_checkpoints`
- `controller_artifacts`

[engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L299)
到 [engine.py](/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py#L319)
则说明 `session_id / account_id / thread_id / agent_id` 只是被写进 run 作为关联 identity。

当前 live 数据也继续支持这个判断：

- `controller_runs` 里有 `130` 条非空 `trace_id`
- 只有 `55` 条非空 `session_id`

所以 `jobdb` 应冻结为：

- **execution correlation truth**

它回答的是：

- 这个 facade session 对应了哪个 run/job
- 当前底层执行状态到底是什么
- work-item/checkpoint/controller artifact index 到了哪里

## 4.4 需要补的精度修正：artifact payload 不在 `jobdb`

这是这次 `v2` 最重要的修正之一。

[db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L771)
已经明确 `controller_artifacts` 只保存：

- `path`
- `uri`
- `metadata_json`

它拥有的是：

- artifact 和 run/work 的关联关系
- artifact 元数据索引

而真正的 payload 则在文件系统里。

[artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L108)
会把 `request.json` 写到：

- `artifacts/jobs/<job_id>/request.json`

[artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L143)
到 [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L243)
则继续把：

- `answer.*`
- `conversation export`
- `result.json`
- `events.jsonl`

写到 `artifacts/jobs/<job_id>/...`

所以这层的准确口径应改成：

- `jobdb` = **artifact correlation/index truth**
- `artifacts/jobs/*` = **artifact payload truth**

这不是第四套 session truth，只是 execution ledger 与 payload store 的正常分层。

## 4.5 `/v2/advisor/*` 仍然没有独立 durable session ledger

这一点保持 `v1` 判断。

[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L500)
和 [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py#L1622)
都只是：

- 接收 `session_id`
- 传给 controller execution

它们没有：

- 类似 `state/agent_sessions` 的 session JSON ledger
- 类似 `/v3/agent/session/*` 的 facade session APIs

所以 `/v2/advisor/ask` 和 `/v2/advisor/advise` 仍然只是：

- **session-aware ingress**

不是第四套 session truth。

## 5. 正式冻结

## 5.1 Session truth owners

### A. OpenClaw runtime continuity truth

当前 owner：

- `OPENCLAW_STATE_DIR`

当前 live path：

- `/home/yuanhaizhou/.home-codex-official/.openclaw`

职责：

- OpenClaw-native runtime continuity
- 上游 runtime identity continuity

结论：

- **A1 Canonical**

### B. Public facade session truth

当前 owner：

- `state/agent_sessions`

职责：

- `/v3/agent/session/*`
- facade-local status / events / stream continuity

结论：

- **A1 Canonical for `/v3/agent/*` surface**

### C. Execution correlation truth

当前 owner：

- `state/jobdb.sqlite3`

职责：

- job / run / work-item / checkpoint ledger
- session to run/job correlation
- artifact index correlation

结论：

- **A1 Canonical for execution correlation**

### D. Artifact payload truth

当前 owner：

- `artifacts/jobs/*`

职责：

- request / answer / result / export / event payload

结论：

- **A1 Canonical for artifact payload content**

注意：

- D 不是新的 session authority
- 它只是 execution sidecar payload store

## 5.2 从现在开始不能再写的话

从现在开始，后续文档不能再写：

- “session truth = 三账本平权”
- “`~/.openclaw` 无条件等于所有 channel continuity truth”
- “jobdb 拥有 artifact payload truth”
- “`state/agent_sessions` 只是缓存，没有 canonical 意义”
- “`/v2/advisor/*` 自己也有独立 durable session ledger”

## 5.3 最终判断

当前系统的最准确说法是：

- **OpenClaw runtime state dir 拥有上游 continuity truth**
- **`state/agent_sessions` 拥有 `/v3/agent/*` facade session truth**
- **`state/jobdb.sqlite3` 拥有 execution correlation truth**
- **`artifacts/jobs/*` 拥有 artifact payload truth**

这不是 split-brain 平权模型。

这是：

- **三层 session truth**
- **外加一层 payload filesystem truth**

## 6. 对后续工作的影响

基于这个 `v2`，后面几件事的边界也更清楚了：

1. `session recovery`
   - OpenClaw 恢复 continuity
   - `/v3/agent/session/*` 恢复 facade session
   - `jobdb` 恢复 execution correlation
   - `artifacts/jobs/*` 保底实际输出 payload
2. `telemetry`
   - 要拆 continuity signals
   - facade session signals
   - execution signals
   - artifact delivery / payload signals
3. `runtime recovery`
   - 不能再试图让 `jobdb` 代替 OpenClaw continuity
   - 也不能让 `state/agent_sessions` 代替 artifact payload truth

## 7. 最小结论

当前系统不是“三套 session truth 打架”，而是：

- **`OPENCLAW_STATE_DIR` = OpenClaw runtime continuity truth**
- **`state/agent_sessions` = public facade session truth**
- **`state/jobdb.sqlite3` = execution correlation truth**
- **`artifacts/jobs/*` = artifact payload truth**

这才是后续继续做 telemetry、runtime recovery、ingress 收敛时应该使用的准确前提。
