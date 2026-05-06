# 2026-04-03 OpenClawBot Planning Task Plane Acceptance Pack Walkthrough v1

## 1. 这轮为什么继续往前做

到 `v15` 为止，planning task plane 已经有了不少 repo-internal proof，但还差一件更值钱的东西：

> `OpenClawBot` 主链到底能不能把 planning task plane 的分配、继续、取回、branch 真跑通。

所以这轮没有再写抽象规划，而是直接做成一个 acceptance pack。

## 2. 我先做了什么

### 2.1 先把 OpenClaw plugin harness 泛化

原来的 `_execute_openclaw_plugin_tool(...)` 只会调：

1. `openmind_advisor_ask`

这不够，因为 planning task plane 主链还需要：

1. `openmind_advisor_task_get`

所以先把 harness 泛化成：

1. 可选 `tool_name`
2. 可选 `tool_params`

这样后面的 pack 才能顺序做：

1. ask
2. get
3. continue
4. get
5. branch
6. get

### 2.2 然后做 OpenClawBot acceptance pack

新增了：

1. `chatgptrest/eval/openclawbot_planning_task_plane_acceptance.py`
2. `ops/export_openclawbot_planning_task_plane_acceptance_pack.py`
3. `tests/test_openclawbot_planning_task_plane_acceptance.py`

这条 pack 不再只打内部 FastAPI，而是：

1. 走 `OpenClaw plugin tool`
2. 通过本地 HTTP proxy 打到真实 `/v3/agent/turn`
3. 再用 plugin 的 `task_get` 取回 checkpoint

## 3. 第一轮碰到的真问题

第一轮不是一把过。

### 3.1 controller 参数假设错了

我一开始假设 controller 看的是 `message`，但真实是 `question`。

结果：

1. pack 第一次直接在 mocked controller 里炸掉
2. 这不是 task plane 坏，而是 acceptance harness 自己的入口假设错了

修法：

1. controller 识别 `question`
2. 保持 `message` 兼容

### 3.2 plugin harness 并发会互踩 `_npx`

当 full export 和 pytest 并行跑时，旧实现会炸：

1. `ENOTEMPTY rename .../esbuild -> .esbuild-*`

这说明 `npx tsx` 之前共享了同一个缓存路径。

修法：

1. 给每次 `_execute_openclaw_plugin_tool(...)` 单独临时 `npm_config_cache`

### 3.3 owner guard 打开后，旧测试和 acceptance helper 没跟上

当我把 `GET /planning/task/{task_id}` 改成 owner-guard 后，两个问题立刻暴露：

1. workforce / implementation 的旧测试还在用错的 `acct/thread`
2. acceptance helper 在 continue 后把 `thread_id` 也换掉了

这两个都不是主链设计错误，而是调用方没跟新契约对齐。

修法：

1. 旧测试改成各自真实 identity
2. acceptance helper 改成：
   - `sessionKey` 可变
   - `thread_id` 稳定

## 4. 这轮真正收住了什么

### 4.1 implicit continue 语义

原来 `_should_continue()` 只要有任意一个材料重叠就继续。

现在改成：

1. `task_type` 必须一致
2. 材料集合的 `Jaccard >= 0.5`

这一步的意义是把“共享模板/公共附件”这类最常见误续接风险先压掉。

### 4.2 task lookup owner guard

原来：

1. 只要知道 `task_id`
2. 任意带 API key 的 caller 都能读

现在：

1. 必须带 identity query
2. 必须和 `record.identity_key` 匹配
3. 否则 `404`

### 4.3 OpenClaw plugin 自动带 identity

如果只在 route 上加 guard，不改 plugin，那就是自己把主链打断。

所以 `openmind_advisor_task_get` 现在会：

1. 从 runtime ctx 提取 identity
2. 自动拼到 `/planning/task/{task_id}?account_id=...&thread_id=...`
3. 无 identity 就 fail-closed

## 5. 这轮证据是什么

### 5.1 定向回归

通过：

1. `tests/test_meeting_task_store.py`
2. `tests/test_routes_agent_v3_meeting_task_layer.py`
3. `tests/test_openclaw_cognitive_plugins.py`
4. `tests/test_openclawbot_planning_task_plane_acceptance.py`
5. `tests/test_openclawbot_meeting_intake_smoke.py`
6. `tests/test_openclaw_dynamic_replay_gate.py`
7. `tests/test_routes_agent_v3_planning_task_plane.py`

### 5.2 full pack

最终 bundle：

1. `docs/dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v1/manifest.json`
2. `docs/dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v1/report_v1.md`

结果是：

1. 7 个 scenario 全通过
2. branch case 通过
3. overall_pass=true

## 6. 这一轮结束后我怎么判断

这轮不是“又做了一个 demo”。

我现在的判断是：

1. planning task plane 已经从 repo-internal proof 升级到了 `OpenClawBot` 主链 proof
2. 当前最直接的 semantic/owner 风险已经被代码收掉
3. 剩下最硬的 runtime 问题，不再是 lookup/continue 这一级，而是更底层的 multi-process durability / file locking
