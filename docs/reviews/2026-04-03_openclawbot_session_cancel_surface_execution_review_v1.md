# 2026-04-03 OpenClawBot Session Cancel Surface Execution Review v1

## 1. 这批改动解决了什么

这批不是再扩 planning task plane，而是把 OpenClawBot owner-path 的 session surface 从“能发起、能查询”补到“能取消”。

完成的点有三条：

1. `openmind-advisor` plugin 新增 `openmind_advisor_session_cancel`。
2. plugin 的 session 摘要 payload 现在保留 `message` 和 `cancelled_job_ids`，避免 cancel 结果回到 OpenClaw 侧变成“只有 status 没有动作上下文”。
3. offline acceptance pack 现在把 `session_cancel` 纳入显式覆盖，不再只验证 `ask / task_get / task_list / session_get / continue`。

对应代码：

- [index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts)
- [acceptance.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/openclawbot_planning_task_plane_acceptance.py)

## 2. 我独立确认成立的事实

### 2.1 owner-path 现在具备完整的会话三元组

从 OpenClawBot 角度，这条窄面现在是：

- 发起：`openmind_advisor_ask`
- 查看：`openmind_advisor_session_get`
- 取消：`openmind_advisor_session_cancel`

而且 `session_cancel` 和 `session_get` 采用同样的 runtime session 限制：

- 没有 runtime session identity 就 fail-closed
- 显式 cross-session id 会 fail-closed

所以它没有把 plugin 重新做回“宽 owner-path 管理台”。

### 2.2 accept pack 不再只验证继续线程，已经开始验证可收口

`export_pack(...)` 现在每个 scenario 都会在 continue 之后显式调用：

- `openmind_advisor_session_cancel`
- 再次 `openmind_advisor_session_get`

并要求两次观察都回到 `cancelled`。

这让 phase-1 的 acceptance 从“能起线程、能找回线程”往前走了一步，开始验证“线程至少能被 owner-path 明确收口”。

### 2.3 这批没有夸大成 live 成功

这次只把：

- plugin surface
- offline acceptance pack
- 相关静态/回归测试

补齐了。

我没有把它说成“live OpenClawBot cancel lane 已经全部验证通过”，因为这批没有去碰 dynamic replay live 失败根因，也没有新增 live cancel gate 证据。

## 3. 验证

通过的检查：

```bash
python3 -m py_compile \
  chatgptrest/eval/openclawbot_planning_task_plane_acceptance.py \
  tests/test_openclawbot_planning_task_plane_acceptance.py \
  tests/test_openclaw_cognitive_plugins.py

./.venv/bin/pytest -q \
  tests/test_openclaw_cognitive_plugins.py \
  tests/test_openclawbot_planning_task_plane_acceptance.py

./.venv/bin/pytest -q \
  tests/test_routes_agent_v3.py::test_agent_cancel_returns_cancelled_lifecycle_surface \
  tests/test_routes_agent_v3.py::test_agent_cancel_bridges_session_cancelled_to_runtime_event_bus \
  tests/test_agent_v3_routes.py
```

## 4. 这批仍然没解决什么

我不把下面这些说成已经解决：

1. live OpenClaw dynamic replay 的 `fetch failed`
2. session cancel 的 live owner-path gate
3. cancel 之后 planning task public status 是否要同步成更强的“task 已收口”语义
4. plugin 侧 task/session surface 是否还需要进一步压缩字段

当前判断：

- 这批是 `W1` owner-path 稳态化里必要的一步，但还不是 live 终局。
- 下一步应该继续回到 live main path，而不是围绕 offline acceptance 再横向扩功能。
