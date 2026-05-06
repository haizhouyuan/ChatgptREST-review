# 2026-03-20 Session Truth Decision Walkthrough v2

## 1. 任务目标

在 [2026-03-20_session_truth_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v1.md) 的基础上，结合：

- [2026-03-20_session_truth_decision_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_verification_v1.md)

做一版更精确的 `v2`。

这次目标不是“顺着核验意见全部改写”，而是：

- 重新回到代码和 live 状态独立判断
- 只吸收被证实的精度问题
- 保留 `v1` 里正确的 layered model

## 2. 这次独立复核的焦点

我重点复核了 4 件事：

1. Layer A 到底能不能直接写成字面 `~/.openclaw`
2. 当前真实 owner 是不是 `OPENCLAW_STATE_DIR`
3. `jobdb` 对 artifacts 的 truth 到底是 index 还是 payload
4. `v1` 的三层模型是否需要推翻

## 3. 这次重新核对的对象

- [runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md#L519)
- [verify_openclaw_openmind_stack.py](/vol1/1000/projects/ChatgptREST/ops/verify_openclaw_openmind_stack.py#L23)
- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts#L194)
- [db.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/db.py#L771)
- [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L108)
- [artifacts.py](/vol1/1000/projects/ChatgptREST/chatgptrest/core/artifacts.py#L243)

同时我又复核了 live 数据：

- `controller_runs` 仍然是 `130` 条非空 `trace_id`
- `55` 条非空 `session_id`
- `state/agent_sessions` 下仍然是 `3` 个 `.json` 和 `3` 个 `.events.jsonl`

## 4. 这次我接受了什么

我接受了两条精度修正：

1. Layer A 不该再冻结成字面 `~/.openclaw`
   - 更准确的是 `OpenClaw runtime state dir / OPENCLAW_STATE_DIR`
   - 当前 live path 是 `/home/yuanhaizhou/.home-codex-official/.openclaw`
2. `jobdb` 不该再说成拥有 artifact payload truth
   - 它拥有的是 artifact correlation/index truth
   - 真正 payload 在 `artifacts/jobs/*`

## 5. 这次我没有接受什么

我没有接受“因为这两处不精确，所以 `v1` 主模型失效”这个推论。

我的独立判断是：

- `v1` 最大的收获是把“session truth = 三账本平权”纠正成 layered model
- 这个主判断仍然成立
- 需要修的只是 Layer A 和 artifact wording

所以 `v2` 的修法不是推翻 `v1`，而是：

- 保留三层 session truth
- 增补 artifact payload filesystem truth

## 6. `v2` 最终收下来的口径

`v2` 最终冻结成：

1. `OPENCLAW_STATE_DIR`
   - OpenClaw runtime continuity truth
2. `state/agent_sessions`
   - public facade session truth
3. `state/jobdb.sqlite3`
   - execution correlation truth
4. `artifacts/jobs/*`
   - artifact payload truth

其中第 4 条不是新的 session ledger，只是 execution sidecar payload store。

## 7. 为什么这版比 `v1` 更稳

因为这次把两个最容易继续误导后续设计的地方修掉了：

- 不再把 Layer A 写成“抽象所有 channel continuity 的字面路径”
- 不再把 execution DB 和 artifact payload store 混成一个 truth owner

这样后面做：

- telemetry contract
- runtime recovery
- front-door / session recovery

才不会继续把 continuity、facade、execution、payload 混在一起。

## 8. 产物

本轮新增：

- [2026-03-20_session_truth_decision_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_v2.md)
- [2026-03-20_session_truth_decision_walkthrough_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_session_truth_decision_walkthrough_v2.md)

## 9. 测试说明

这次仍然是文档与代码证据校正任务，没有改代码，也没有跑测试。
