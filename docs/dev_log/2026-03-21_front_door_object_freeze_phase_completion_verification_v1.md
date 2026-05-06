# 2026-03-21 Front Door Object Freeze Phase Completion Verification v1

## 结论

`Phase 1: Front Door Object Freeze` 的 live ingress 实现面基本成立，但当前阶段完成口径仍然略强，不能把整块 compatibility surface 直接判成“完全 freeze”。

更准确的判断是：

- `task_intake.py`、`routes_agent_v3.py`、`routes_advisor_v3.py`、`standard_entry.py` 这一条 live / adapter 主链已经收敛完成
- `task_spec.py` 已明显转向 canonical bridge
- 但 `task_spec.py` 还没有完全 fail-closed 成“只能从 canonical intake 派生”的兼容桥

## Findings

### 1. `task_spec.py` 仍允许直接旁路构造 `TaskSpec`

这意味着阶段完成文档里“`IntentEnvelope -> Task Intake Spec -> TaskSpec` 已成为唯一主线”的说法还不够精确。

当前代码里：

- `TaskSpec` 仍是可直接实例化的公开 `BaseModel`
- `task_intake` 字段仍然是可选字段
- 现有测试仍显式覆盖 `TaskSpec(user_intent=\"test\")` 与 `TaskSpec(..., mode=\"autonomous\")` 这类直接构造路径

直接证据：

- `chatgptrest/advisor/task_spec.py:97`
- `chatgptrest/advisor/task_spec.py:148`
- `tests/test_system_optimization_v2.py:78`
- `tests/test_system_optimization_v2.py:85`

这不是当前 live ingress bug，因为 repo 内我没有找到生产路径在直接 new `TaskSpec(...)`。但从“前门对象 freeze 已完全完成”的架构口径看，它仍然保留了旁路入口。

### 2. canonical intake 到 `TaskSpec` 的桥接仍然会丢 `priority`

`TaskIntakeSpec` 已包含 canonical `priority`，但 `task_intake_to_task_spec(...)` 当前没有把它传到 `TaskSpec.priority`，导致 bridge 不是无损桥接。

我本地复核的最小复现是：

- canonical intake 传入 `priority=1`
- 转成 `TaskSpec` 后 `priority` 变回默认值 `5`

直接证据：

- `chatgptrest/advisor/task_intake.py:104`
- `chatgptrest/advisor/task_intake.py:213`
- `chatgptrest/advisor/task_spec.py:151`
- `chatgptrest/advisor/task_spec.py:221`

这同样不是当前 `/v3/agent/turn` 或 `/v2/advisor/ask` 的阻断性问题，但它说明 `task_spec.py` 作为 compatibility bridge 仍然有一处字段语义没有完全对齐 canonical intake。

## 已核实成立的部分

以下实现判断我已重新核实，结论成立：

- seeded `AskContract` 不再把 `research/report/code_review/image/consult/repair` 打回 `general`
- caller 显式传错 `task_intake.spec_version` 时，两条 live 入口都会返回 `400`
- generic `thread_id + agent_id` 不再把普通 REST 流量误判成 `openclaw`
- `standard_entry.py` 已收为 legacy adapter，并会附着 canonical `task_intake`
- `routes_agent_v3.py` 与 `routes_advisor_v3.py` 现在都以 shared normalizer 为共同 ingress 目标

## 评审判断

如果把验收目标定义为“公开 live ingress 主链已经统一到 canonical front-door object”，这轮可以通过。

如果把验收目标定义为“所有兼容对象都已经彻底降为只能桥接 canonical intake，且 bridge 语义无损”，这轮还差最后一小步，不应把阶段口径写满。

因此本轮建议的最准确结论是：

- `Phase 1` 的 live ingress freeze 已完成
- `Phase 1` 的 compatibility bridge freeze 尚未 100% 收口
- 下一步若继续收尾，优先级最高的是：
  - 让 `TaskSpec` 直接构造路径显式降级或标注为 compatibility-only
  - 让 `task_intake_to_task_spec(...)` 保留 canonical `priority`

## 本轮复跑核验

我重新执行并通过了以下回归：

```bash
./.venv/bin/pytest -q \
  tests/test_task_intake.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_agent_v3_routes.py \
  tests/test_system_optimization_v2.py

./.venv/bin/pytest -q tests/test_system_optimization.py -k 'StandardEntry'

python3 -m py_compile \
  chatgptrest/advisor/task_intake.py \
  chatgptrest/advisor/standard_entry.py \
  chatgptrest/advisor/task_spec.py \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/api/routes_advisor_v3.py \
  tests/test_task_intake.py \
  tests/test_routes_agent_v3.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_system_optimization.py \
  tests/test_system_optimization_v2.py
```

另外，本地最小复现也确认：

- 直接 `TaskSpec(user_intent=\"manual path\")` 仍然合法，且 `task_intake is None`
- `build_task_intake_spec(... priority=1) -> task_intake_to_task_spec(...)` 后，`TaskSpec.priority == 5`
