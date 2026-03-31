# 2026-03-20 Front Door Object Contract Walkthrough v1

## 做了什么

这轮把 `Phase 1` 的前 3 个交付物一起落了：

- [front_door_object_contract_v1](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_front_door_object_contract_v1.md)
- [task_intake_spec_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_task_intake_spec_v1.json)
- [entry_adapter_matrix_v1](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_entry_adapter_matrix_v1.md)

## 为什么这轮先写对象契约

因为当前真正没收住的不是 route authority，而是入口对象本身：

- `task_spec.py` 里已经有 `IntentEnvelope / TaskSpec`
- `standard_entry.py` 里又有 `StandardRequest`
- `/v3/agent/turn` 还在直接吃 free-form body + scattered contract fields
- `AskContract` 又承担了 clarify / strategist / prompt/review 的核心字段

如果不先冻结 canonical object，后面的 `planning / research scenario pack` 只会继续在不同入口上长不同字段。

## 这轮的独立判断

### 1. `Task Intake Spec` 应该是 canonical

原因：

- 它最接近“入口统一对象”的正确层级
- 比 `AskContract` 更适合承载 identity / context / attachments / acceptance / evidence
- 比 `StandardRequest` 更完整

### 2. `AskContract` 不该废弃

但它应该收缩成 reasoning view，而不是平行真相源。

它现在的字段刚好适合：

- strategist clarify
- prompt builder
- post-review

所以这轮不是否定 `AskContract`，而是给它降权。

### 3. `standard_entry.py` 不能再长大

它更像历史阶段的轻量 normalizer 和 skill/preset precheck carrier，不适合再升级成 canonical object system。

## 参考了哪些代码

- [task_spec.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/task_spec.py)
- [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py)
- [ask_contract.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_contract.py)
- [ask_strategist.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/ask_strategist.py)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)
- [routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_advisor_v3.py)
- [openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)

## 下一步怎么接

这轮文档冻结后，下一步就不是再讨论概念，而是按矩阵开实现：

1. 把 shared intake normalizer 放到 canonical path
2. 先让 `routes_agent_v3.py` 吃 `task_intake`
3. 再让 `/v2/advisor/ask` 复用同一 normalizer
4. 最后再改 OpenClaw plugin payload

## 边界

这轮没有改代码实现，只冻结了 Phase 1 的对象契约和 adapter 基线。后续若根据实现反馈修订，必须出 `v2`，不能覆盖这组文件。
