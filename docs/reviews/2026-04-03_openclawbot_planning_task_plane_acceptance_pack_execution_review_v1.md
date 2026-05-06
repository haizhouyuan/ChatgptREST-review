# 2026-04-03 OpenClawBot Planning Task Plane Acceptance Pack Execution Review v1

## 1. 这一步做了什么

这一步不是再加新的 planning task 功能，而是把 `OpenClawBot -> openmind-advisor -> /v3/agent/turn -> planning task plane -> task_get/continue/branch` 这条主链压成了真实 acceptance pack。

本次成立的事实有 4 个：

1. `OpenClawBot` 插件入口现在不只证明了 `meeting intake`，而是证明了 7 类 planning task type 都能从插件主链分配、继续、取回。
2. `project_diagnosis -> leadership_report` 的 branch 也有了主链 evidence。
3. `GET /v3/agent/planning/task/{task_id}` 现在加上了 owner guard，不再允许无 identity 或错 identity 直接读回。
4. `_should_continue()` 不再是“单个材料重叠就继续”，而是收紧到了 “task_type 一致 + 材料重合度足够高”。

## 2. 这次实际改了什么

### 2.1 planning task store

[meeting_task_store.py](/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py)

这次对 `MeetingTaskStore` 做了两类收口：

1. `get_public(...)`
   - 增加 `account_id / thread_id / user_id / session_id`
   - 无 identity 或 identity 不匹配时直接 fail-closed
2. `_should_continue(...)`
   - 新增 `task_type` 约束
   - 不再只看 “是否有任意一个材料重叠”
   - 现在要求 `existing/incoming` 的材料集合 `Jaccard >= 0.5`

这一步的目标不是发明完美语义，而是先把最明显的“共享模板/公共附件导致误续接”风险压掉。

### 2.2 agent route

[routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py)

`GET /v3/agent/planning/task/{task_id}` 现在要求显式 identity query：

1. `account_id`
2. `thread_id`
3. 或者 `user_id / session_id`

当前行为是：

1. identity 缺失 -> `404`
2. identity 不匹配 -> `404`
3. identity 匹配 -> 返回 `planning_task`

这一步是高 blast-radius 文件上的窄改动。GitNexus 对 `make_v3_agent_router` 给的是 `CRITICAL`，所以本次只改了这条 lookup route 的 query/guard，不顺手碰其它 surface。

### 2.3 OpenClaw plugin

[index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)

`openmind_advisor_task_get` 现在不再裸调 `task_id`：

1. 会从 runtime ctx 恢复 `account_id / thread_id / user_id / session_id`
2. 自动带到 `/v3/agent/planning/task/{task_id}?...`
3. 如果拿不到 runtime identity，直接 fail-closed

这样 owner guard 不会把 `OpenClawBot` 主链自己打断。

### 2.4 acceptance harness

新增：

1. [openclawbot_planning_task_plane_acceptance.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclawbot_planning_task_plane_acceptance.py)
2. [export_openclawbot_planning_task_plane_acceptance_pack.py](/vol1/1000/projects/ChatgptREST/ops/export_openclawbot_planning_task_plane_acceptance_pack.py)
3. [test_openclawbot_planning_task_plane_acceptance.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_planning_task_plane_acceptance.py)

这条 acceptance pack 证明的是：

1. 插件入口是真实入口，不是直打 FastAPI TestClient
2. `task_get`
3. `explicit_continue`
4. `branch`
5. `source_material capture`
6. `checkpoint_version`

都能在 OpenClaw 插件主链上被证明

### 2.5 plugin harness concurrency

[openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclaw_dynamic_replay_gate.py)

这次还顺手补掉了一个真实 runtime 脆弱点：

1. 旧实现靠 `npx tsx`
2. 并发跑 export / pytest 时会抢同一个 `_npx/esbuild` 目录
3. 结果是 `ENOTEMPTY rename .../esbuild -> .esbuild-*`

现在 `_execute_openclaw_plugin_tool(...)` 每次都走自己的临时 `npm_config_cache`，并发不再互踩。

## 3. 这一步我接受了哪些 red-team 意见

这一步明确接受并落到代码的是：

1. `_should_continue` 过宽
2. `task lookup` 没有 owner guard

我没有在这一步里继续扩大成：

1. 多进程文件锁
2. repo 级 canonical task runtime
3. 把 `OpenClawBot` 做成 orchestration facade

原因很简单：

1. 这一步聚焦的是 planning task plane 主链可用性与 owner boundary
2. 多进程文件锁确实是下一个真实问题，但属于下一批 runtime hardening

## 4. 本地验证

### 4.1 定向回归

通过：

1. [test_meeting_task_store.py](/vol1/1000/projects/ChatgptREST/tests/test_meeting_task_store.py)
2. [test_routes_agent_v3_meeting_task_layer.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_meeting_task_layer.py)
3. [test_openclaw_cognitive_plugins.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_cognitive_plugins.py)
4. [test_openclawbot_planning_task_plane_acceptance.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_planning_task_plane_acceptance.py)
5. [test_openclawbot_meeting_intake_smoke.py](/vol1/1000/projects/ChatgptREST/tests/test_openclawbot_meeting_intake_smoke.py)
6. [test_openclaw_dynamic_replay_gate.py](/vol1/1000/projects/ChatgptREST/tests/test_openclaw_dynamic_replay_gate.py)
7. [test_routes_agent_v3_planning_task_plane.py](/vol1/1000/projects/ChatgptREST/tests/test_routes_agent_v3_planning_task_plane.py)

### 4.2 full acceptance pack

真实 evidence bundle：

1. [manifest.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v1/manifest.json)
2. [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v1/report_v1.md)

当前结果：

1. `7/7` 场景通过
2. `branch_case` 通过
3. `overall_pass=true`

### 4.3 并发稳定性

这轮还额外证明了一点：

1. pytest 和 full export 并发跑时
2. 两个 `tsx` harness 会同时存活
3. 但不会再因为共享 `_npx` 缓存而互相炸掉

## 5. 这一步之后，当前口径怎么改

更准确的说法应改成：

1. planning task plane 现在已经不只是 repo-internal proof
2. `OpenClawBot` 主链上已经有 `7 task types + explicit continue + task_get + branch` 的真实 acceptance evidence
3. 同时，task lookup boundary 也不再是 open-read

但仍然不要夸大成：

1. multi-process durability 已经彻底解决
2. full task runtime 已经取代当前 sidecar truth
3. 所有长期并发问题都已收口

## 6. 一句话结论

这一步把 planning task plane 从“内部可证明”推进到了“OpenClawBot 主链可证明”，同时把两个最直接的 semantic/owner 风险收进了代码：`implicit continue` 不再过宽，`task lookup` 不再 open-read。
