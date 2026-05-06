# 2026-03-21 Shared Task Intake Normalizer v1

## 1. 这轮做了什么

这轮把 `Phase 1` 的第一段实现真正接进了 live 路径：

- 新增共享 canonical intake 模块：
  - [task_intake.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py)
- `/v3/agent/turn` 现在会先归一出 versioned `Task Intake Spec v2`
  - [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- `/v2/advisor/ask` 现在也会归一出同一份 `Task Intake Spec v2`
  - [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)

这不是最终 front-door 重构完成版，但已经把 shared intake normalizer 从文档层推进到了代码层。

## 2. 为什么这样落

当前 live 系统里，`task_spec.py` 还没有和 `Task Intake Spec v2` 对齐。

所以这轮没有直接硬改：

- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py)
- [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py)

而是新建一个更窄的共享模块，把 implementation 风险压低：

- 先让 live ingress 共享同一个 canonical intake normalizer
- 后面再决定如何把旧 carrier 收编进去

这是为了避免一上来就把 `agent_v3`、`advisor_ask`、`task_spec.py`、`standard_entry.py` 一起搅动。

## 3. 这轮的独立判断

### 3.1 先接 live ingress，比先改旧模型更重要

如果现在先大改 `task_spec.py`，风险会落到“旧对象语义变了，但 live 路径还没统一使用它”。

这轮反过来做：

- 先统一 live ingress
- 后续再收编旧对象

更稳。

### 3.2 `Task Intake Spec v2` 先作为 adapter target，不先作为 controller API

这轮没有改 `ControllerEngine.ask(...)` 接口。

而是把 canonical intake 先双写到：

- `stable_context["task_intake"]`
- `request_metadata["task_intake"]`

这样下游：

- 已经能拿到 canonical object
- 但 controller / route / execution 的接口 blast radius 不会一下子放大

## 4. 具体实现

### 4.1 新模块

[task_intake.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_intake.py) 提供了 4 类能力：

- versioned `TaskIntakeSpec`
- `AcceptanceSpec` / `EvidenceRequirementSpec`
- `build_task_intake_spec(...)`
- `task_intake_to_contract_seed(...)`

### 4.2 Source 归一

实现了 v2 文档里冻结的 source 归一规则：

- canonical source enum
- legacy `codex / api / direct` 映射
- OpenClaw runtime marker 优先级
- client-name 中 `mcp` 的 heuristic fallback

### 4.3 `/v3/agent/turn`

接法：

- 先从 body/context/identity 归一出 `Task Intake Spec v2`
- 把 canonical intake 写进 `context["task_intake"]`
- 再从 intake 派生 `contract_seed`
- 最后和兼容层 `contract/top-level fields` 合并，喂给 `normalize_ask_contract(...)`

这意味着：

- `AskContract` 仍保留
- 但它开始真正从 canonical intake 派生，而不是只靠 scattered body fields

### 4.4 `/v2/advisor/ask`

接法：

- 在 `merged_context / stable_context` 完成后构建 canonical intake
- 为了不污染既有 idempotency hash，这一步放在 `request_fingerprint / stable_context_hash` 之后
- 然后把 canonical intake 注入 `stable_context` 和 `request_metadata`

这样做的结果是：

- graph/controller path 已能消费 canonical intake
- 但这轮没有改变它的外部响应契约

## 5. 没做什么

这轮明确没做：

- 没把 `task_spec.py` 改写成 `Task Intake Spec v2`
- 没把 `standard_entry.py` 改成 canonical normalizer
- 没改 `ControllerEngine.ask(...)` 参数结构
- 没改 OpenClaw plugin payload
- 没动 Feishu WS route

这些都留在后续阶段。

## 6. 测试

新增测试：

- [test_task_intake.py](/vol1/1000/projects/ChatgptREST/tests/test_task_intake.py)
- [test_routes_advisor_v3_task_intake.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_advisor_v3_task_intake.py)
- [test_routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3.py)

通过的定向回归：

```bash
./.venv/bin/pytest -q \
  tests/test_task_intake.py \
  tests/test_routes_agent_v3.py \
  tests/test_agent_v3_routes.py \
  tests/test_routes_advisor_v3_task_intake.py \
  tests/test_routes_advisor_v3_security.py

./.venv/bin/pytest -q tests/test_advisor_v3_end_to_end.py -k 'v3_ask_'

python3 -m py_compile \
  chatgptrest/advisor/task_intake.py \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/api/routes_advisor_v3.py \
  tests/test_task_intake.py \
  tests/test_routes_advisor_v3_task_intake.py
```

## 7. 下一步

最自然的下一步是：

1. 让 `standard_entry.py` 复用 `task_intake.py`
2. 让 `/v3/agent/turn` 接受显式 `task_intake` 作为一等 payload，而不是主要靠顶层散字段
3. 再决定是否把 `task_spec.py` 收编到 canonical module
