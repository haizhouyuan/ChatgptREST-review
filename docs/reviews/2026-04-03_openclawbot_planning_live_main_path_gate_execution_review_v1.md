# 2026-04-03 OpenClawBot Planning Live Main-Path Gate Execution Review v1

## 1. 这批改动解决了什么

这批把 `W1` 从 `synthetic owner-path live gate green` 往前推进到了
`closer-to-real OpenClaw main-path gate green`。

关键不是又加了一个新 gate，而是修掉了一个真实的 main-path bug：

- `openmind_advisor_task_get`
- `openmind_advisor_task_list`
- `openmind_advisor_session_get`
- `openmind_advisor_session_cancel`

在 `resolvePluginTools -> toToolDefinitions` 这条路径下，没有从注入的
`params.context` 读取 runtime identity，因此：

- task surfaces 会带着错误 identity 去查，出现 `count=0 / 404`
- session surfaces 会直接报 `runtime session identity required`

修复后，这条 closer-to-real 的 OpenClaw main path 已经能真实跑通：

- `ask`
- `task_list`
- `task_get`
- `session_get`
- `session_cancel`

## 2. 我独立确认成立的事实

### 2.1 之前 v1 的失败不是“没有 landing”，而是 main-path identity 断了

我先用 raw main-path 调用逐个核过：

- `openmind_advisor_ask` 实际已经返回了真实 `task_id`
- 对应 planning task 也确实已经落盘到 `state/planning_tasks/`
- 但后续 `task_list/task_get/session_*` 在 main-path 下用的是错误 identity

所以旧 artifact `v1` 的失败，不能解读成“OpenClaw main path 根本没有落到 planning task plane”。
更准确的说法是：

> ask 已经 landed，但 main-path 下的 task/session query surfaces 还没有正确继承 runtime identity。

### 2.2 修复后 v2 live artifact 已经真实跑绿

真实 artifact：

- [manifest.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_main_path_gate_20260403_v2/manifest.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_main_path_gate_20260403_v2/report_v1.md)

关键结果：

- `ok=true`
- `num_checks=5`
- `num_failed=0`

通过的 5 条检查是：

- `main_path_live_ask_observable`
- `main_path_task_list_visible`
- `main_path_task_get_visible`
- `main_path_session_observable`
- `main_path_session_cancel_observable`

### 2.3 这次 green 的意义比 owner-path 更接近真实 OpenClaw 使用法

这条 gate 不是直接调 plugin `spec.execute`，而是走：

- `resolvePluginTools`
- `toToolDefinitions`
- main-path tool execute

所以它比 owner-path synthetic gate 更接近 OpenClawBot 真正使用 plugin tool 的方式。

我当前签这句话：

> integrated host 上，OpenClaw main-path 已能把 planning task plane 的 ask/query/cancel triad 跑通。

### 2.4 但它仍然不是 Feishu 聊天面证明

我当前仍然不签这些更大的话：

- Feishu/OpenClawBot 聊天入口已经 live 证明
- final completion / answer quality 已证明
- 第一阶段整体目标已达成

这批只证明：

- main-path tool wiring 是通的
- task/session continuity query surfaces 在 closer-to-real 路径下可用

## 3. 代码层面的关键改动

### 3.1 plugin 侧补了 injected params.context 的 runtime identity 继承

文件：

- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)

新增了 `paramsContext(...)`，并让下面 4 个 tool surface 都改为：

- 从 `params.context` 读取 injected runtime identity
- 再交给 `deriveRuntimeContext(...)`

对应 surface：

- `openmind_advisor_task_get`
- `openmind_advisor_task_list`
- `openmind_advisor_session_get`
- `openmind_advisor_session_cancel`

### 3.2 main-path runner 改为写入 v2 artifact 目录

文件：

- [run_openclawbot_planning_task_plane_live_main_path_gate.py](/vol1/1000/projects/ChatgptREST/ops/run_openclawbot_planning_task_plane_live_main_path_gate.py)

这样不会覆盖前一版失败证据，便于后续复盘：

- `..._v1` 保留失败现场
- `..._v2` 保留修复后 green 现场

## 4. 验证

通过的回归：

```bash
python3 -m py_compile   chatgptrest/eval/openclawbot_planning_task_plane_live_main_path_gate.py   ops/run_openclawbot_planning_task_plane_live_main_path_gate.py   tests/test_openclaw_cognitive_plugins.py   tests/test_openclawbot_planning_task_plane_live_main_path_gate.py   tests/test_run_openclawbot_planning_task_plane_live_main_path_gate.py

./.venv/bin/pytest -q   tests/test_openclaw_cognitive_plugins.py   tests/test_openclawbot_planning_task_plane_live_main_path_gate.py   tests/test_run_openclawbot_planning_task_plane_live_main_path_gate.py

./.venv/bin/pytest -q   tests/test_openclawbot_planning_task_plane_acceptance.py   tests/test_routes_agent_v3_planning_task_plane.py
```

真实 live 运行：

```bash
python3 ops/run_openclawbot_planning_task_plane_live_main_path_gate.py
```

## 5. 仍未解决的部分

这批完成后，仍未解决的是：

1. 真正 Feishu/OpenClawBot 聊天面的 live 证明
2. planning lane final completion / answer quality 的 live 证明
3. provider coverage 的 phase-1 口径收口
4. 第一阶段整体 acceptance pack 的最终全绿

所以这批的正确定位是：

- 它把 `W1` 从 owner-path synthetic live 进一步推进到了 closer-to-real main-path live
- 但还没有越过到真实 Feishu 入口和最终 completion quality
