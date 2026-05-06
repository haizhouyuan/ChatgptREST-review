# 2026-03-21 Standard Entry Task Intake Alignment Walkthrough v1

## 为什么先收这个点

`standard_entry.py` 本来就是“多入口统一 adapter”，但它之前还停留在旧 carrier 语义里。  
如果不先把它和 shared intake normalizer 对齐，后面前门对象会继续出现两套理解：

- live ingress 用 canonical `task_intake`
- standard entry 还在产出 legacy-only request

这会让下一阶段的对象收敛继续漂。

## 风险判断

这轮 GitNexus impact 是 `LOW`：

- `StandardRequest`
- `normalize_request`
- `standard_entry_pipeline`
- `process_codex_request`
- `process_mcp_request`

主要只挂在 [tests/test_system_optimization.py](/vol1/1000/projects/ChatgptREST/tests/test_system_optimization.py) 上，不在当前 live ingress 热路径里。

所以这轮策略是：

- 不改 wider runtime
- 不改 controller
- 只把 canonical intake 作为附着对象接进 `standard_entry`

## 关键决策

### 1. 不把 `StandardRequest` 直接改成 canonical object

如果现在直接让 `StandardRequest` 本身变成 canonical front-door object，等于把旧 adapter 彻底推倒重来。

这轮没有这么做。  
而是让它保留 legacy carrier 身份，再附着 `task_intake`。

### 2. 不改 legacy `source` 输出

`process_codex_request(...)` 现在仍然返回：

- `result["source"] == "codex"`
- `dispatch_params["source"] == "codex"`

但 canonical source 已经在 `dispatch_params["task_intake"]["source"]` 里变成了 `cli`。

这是刻意的双轨过渡，不是遗漏。

## 结果

这轮完成后，`standard_entry` 不再是 canonical intake 体系之外的旧角落。

它现在已经进入同一条对象线，只是还保留了旧 carrier 皮肤。  
这让后续是否彻底降级 legacy `source`，可以作为下一阶段单独决策，而不是继续混着漂。
