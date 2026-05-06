# 2026-04-01 ChatgptREST 定位漂移代码与运行态独立复核 v2

## 为什么出 v2

`v1` 结论的大方向是对的，但在 peer review 后有两点需要收紧：

1. `advisor_v3=18713` 不只是旧文档残留，而是已经污染到机器可读治理输出。
2. 这种污染的直接链路不是 `scripts/chatgptrest_bootstrap.py` 的人类可读 markdown 摘要，而是：
   - `ops/registries/runtime_registry.yaml`
   - `ops/health_checks.py`
   - `chatgptrest.repo_cognition.runtime.generate_runtime_snapshot()`
   - 最终进入 `bootstrap-v1` packet 的 `runtime_snapshot.services`

所以 v2 的重点不再只是“复盘发现了什么”，而是“哪些 peer review 点成立，以及我已经把哪条错误 runtime fact 修掉了”。

## Peer Review 处置

### 处置 1

第一份 review 的高优判断成立，而且应该升级为代码 bug，而不是只算复盘补充。

我重新核实后的事实链是：

1. `runtime_registry.yaml` 仍把 `advisor_v3` 写成 `127.0.0.1:18713`
2. `ops/health_checks.py` 会把某些 `404` 记成 liveness success
3. `summarize_runtime_quick()` 直接把这个结果写进 `runtime_snapshot.services`
4. `scripts/chatgptrest_bootstrap.py --runtime quick` 会把这个 packet 原样回给 agent

也就是说，问题不只是“人写错了”，而是：

> 机器治理链曾经真的会向 agent 回传错误 runtime fact

### 处置 2

第二份 review 有一个边界纠正是对的：

- `scripts/chatgptrest_bootstrap.py` 自己的 markdown 摘要并不会单独把 `advisor_v3=18713` 文字打印出来
- 真正受污染的是 `bootstrap-v1` packet 里的 `runtime_snapshot.services`

所以更准确的口径应该是：

> stale fact 确实污染了 bootstrap 主链，但污染点在 quick runtime snapshot，而不是 bootstrap markdown summary 的单独格式化层。

### 处置 3

关于 `workspace` 的 peer review，我采纳“要加时效边界”这一点。

更准确的说法是：

- `workspace` 作为 side-effect / delivery plane 的接线是真实架构事实
- `WorkspaceService().auth_state()` 在 `2026-04-01` 返回 `invalid_grant`，这是 live runtime 时点事实，不应被写成静态架构事实

## 已实施修复

本轮我直接修了三处机器治理链：

### 1. 修 `runtime_registry.yaml`

把 `advisor_v3` 从过时的 `18713` 改成统一 FastAPI host 上的 `18711`：

- `ops/registries/runtime_registry.yaml`

修复后：

- `liveness_url = http://127.0.0.1:18711/v2/advisor/health`
- `agent_entry_url = http://127.0.0.1:18711`
- `port = 18711`

### 2. 修 `ops/health_checks.py`

不再把所有 `404` 一律当作 liveness success。

现在的规则是：

- `401 / 403 / 405` 默认仍可作为 alive
- `404` 只对根路径 probe 视为 alive，例如 bare MCP `/`
- 对 `/v2/advisor/health` 这类具体服务路径，`404` 现在默认为 unhealthy

这条修复避免以后再把“错误服务上的 404”误判成“目标服务活着”。

### 3. 修 `maint_memory`

把 maint bootstrap memory 里的过时端口口径改掉：

- `chatgptrest/ops_shared/maint_memory.py`

原来是：

- `advisor_v3=0.0.0.0:18713`

现在改成：

- `advisor_v3_surface=127.0.0.1:18711/v2/advisor/*`

### 4. 修活动维护文档

这轮我也顺手修了两份仍会继续指导维护者的活动文档：

- `AGENTS.md`
- `docs/ops/feishu_webhook_binding.md`

修复原则是：

- 把集成态默认入口统一写成 `18711`
- 明确 `18713` 只应被视为“显式单独起 dedicated advisor 服务时的可选端口”
- 不再把 `18713` 写成当前维护默认事实

### 5. 修 deep runtime probe 的 advisor 漏检

peer review 之后我又补做了一轮代码审查，发现还有一处不该留着的治理缺口：

- `ops/health_probe.py` 的 deep probe 之前只检查 `api_18711`、`dashboard_8787`、`mcp_18712`
- 它没有把 `advisor_v3` 单独纳入 `all_ok`
- 结果就是 quick snapshot 即使已经把 advisor 标成异常，deep summary 的总健康位也可能漏报

这轮已经补上：

- deep probe 现在显式检查 `http://127.0.0.1:18711/v2/advisor/health`
- 并新增失败路径测试，确保 `advisor_v3` 不健康时 `all_ok` 会降为 `False`

## 回归验证

### 代码级回归

我新增并通过了以下定向测试：

- `tests/test_health_checks.py`
- `tests/test_health_probe.py`
- `tests/test_maint_bootstrap_memory.py`

并复跑通过：

- `tests/test_repo_cognition_runtime.py`
- `tests/test_chatgptrest_bootstrap.py`
- `tests/test_agent_mcp.py`
- `tests/test_health_probe.py`

### 运行态回归

我重新执行：

- `python scripts/chatgptrest_bootstrap.py --task 'validate runtime fact repair' --runtime quick`

修复后的 `runtime_snapshot.services` 已变成：

- `advisor_v3.ok = true`
- `advisor_v3.port = 18711`
- `advisor_v3.agent_entry_url = http://127.0.0.1:18711`

也就是说：

> bootstrap packet 不再把 `advisor_v3=18713` 作为 runtime fact 暴露给 agent。

## 更新后的独立判断

`v1` 的主结论我保留，不改：

- `ChatgptREST` 已经不是单一 OpenClaw 插件后端
- 它已经是多平面集成宿主
- 真问题是多个真实平面已经并存，但 authority matrix 没冻结

但我现在把优先级顺序调整为：

1. 先修机器治理 false-positive runtime facts
2. 再写 authority matrix / retirement matrix

因为在 agent 系统里，错误的 machine-readable runtime fact 比 prose drift 更危险。

但这不意味着 prose drift 可以不管。像 `AGENTS.md` 这种活动维护文档，如果继续保留旧端口口径，就会把下一轮 agent 再次带偏。

## 当前冻结口径

如果要给这轮复核一个更稳的收口句，我会用这句：

> ChatgptREST 的核心问题已经不只是“架构定位漂移”，而是“架构漂移一度进入了机器治理链”。这一点现在已完成首轮修复：bootstrap quick runtime snapshot 不再把 advisor_v3=18713 当成 live runtime fact；接下来才应该继续冻结 authority matrix、completion authority 和 subsystem retirement 边界。
