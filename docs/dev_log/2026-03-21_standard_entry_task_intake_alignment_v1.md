# 2026-03-21 Standard Entry Task Intake Alignment v1

## 1. 这轮做了什么

这轮把 [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py) 接到了 shared `task_intake` normalizer 上，但没有把它改造成新的 canonical carrier。

实现后的定位是：

- `StandardRequest` 继续保留 legacy adapter carrier 身份
- `task_intake` 作为 canonical front-door object，附着在 `StandardRequest` 上

## 2. 为什么这样做

前一轮已经把 live ingress：

- `/v3/agent/turn`
- `/v2/advisor/ask`

统一到了 shared `task_intake` 模块。

下一步最自然的收编对象就是 `standard_entry.py`，因为它本来就是“多入口 adapter”，但之前仍在输出 legacy `source=codex/api/direct` 这套 carrier 语义。

这轮没有直接推翻 `StandardRequest`，而是把 canonical intake 作为附着对象挂进去，原因是：

- blast radius 低
- 现有测试主要围绕 adapter 行为
- 可以先对齐对象模型，再决定是否彻底收编旧 carrier

## 3. 具体实现

### 3.1 `StandardRequest` 新增 canonical intake 附着位

文件：

- [standard_entry.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/standard_entry.py)

新增：

- `task_intake: TaskIntakeSpec | None`

这让 `StandardRequest` 继续保留：

- `question`
- `source`
- `target_agent`
- `preset`

这些 legacy adapter 字段，同时又能携带 canonical object。

### 3.2 `normalize_request(...)` 现在直接复用 shared normalizer

`normalize_request(...)` 现在会：

1. 生成/确定 `trace_id`
2. 从 `metadata` 中提取可选 `task_intake`
3. 调用 `build_task_intake_spec(...)`
4. 把生成的 canonical intake 挂到 `request.task_intake`

这里保留了 legacy source carrier，但 canonical source 会在 `task_intake` 内被重新归一：

- `codex -> cli`
- `api -> rest`
- `direct -> unknown`

### 3.3 pipeline 和 dispatch params 都开始带 canonical object

`standard_entry_pipeline(...)` 现在会额外输出：

- `result["task_intake"]`
- `result["task_intake_summary"]`
- `dispatch_params["task_intake"]`

但不会改掉原本的：

- `result["source"]`
- `dispatch_params["source"]`

这样做是为了保证旧 adapter/tests 不炸，同时让 downstream 已经拿得到 canonical object。

## 4. 这轮没做什么

这轮明确没做：

- 没把 `StandardRequest.source` 改成 canonical enum
- 没删除 `codex/api/direct` 这些 legacy source 值
- 没把 `standard_entry` 直接接到 controller/live runtime
- 没改 `task_spec.py`

## 5. 测试

更新了 [tests/test_system_optimization.py](/vol1/1000/projects/ChatgptREST/tests/test_system_optimization.py) 中的 `StandardEntry` 测试，新增验证：

- `normalize_request(...)` 会生成 canonical `task_intake`
- 错误 `task_intake.spec_version` 会显式失败
- `process_mcp_request(...)` 会输出 `task_intake_summary`
- `dispatch_params` 会透传 canonical `task_intake`

通过：

```bash
./.venv/bin/pytest -q tests/test_system_optimization.py -k 'StandardEntry'
python3 -m py_compile chatgptrest/advisor/standard_entry.py tests/test_system_optimization.py
```

## 6. 结果

`standard_entry.py` 现在已经和 shared intake normalizer 对齐，但还是以“legacy adapter carrier + canonical attachment”的过渡形态存在。

这意味着下一步如果要继续收编：

1. 可以先让更多非 live adapter 统一写出 `task_intake`
2. 再决定何时把 legacy `source`/carrier 彻底降级
