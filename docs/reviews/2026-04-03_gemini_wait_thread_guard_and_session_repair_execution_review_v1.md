# 2026-04-03 Gemini Wait Thread Guard And Session Repair Execution Review v1

## 1. 本轮完成了什么

这轮不是继续扩 planning 能力面，而是专门收 `OpenClawBot planning live completion gate` 暴露出来的真实错答风险。

完成的代码改动只有两类：

1. `Gemini wait/export` 增加 thread guard  
   文件：
   - `chatgpt_web_mcp/providers/gemini/wait.py`

2. `public session/job projection` 把 `GeminiConversationThreadMismatch` 收成 `needs_followup + same_session_repair`  
   文件：
   - `chatgptrest/api/routes_agent_v3.py`

对应新增/更新测试：

- `tests/test_gemini_wait_param_compat.py`
- `tests/test_gemini_wait_conversation_url_upgrade.py`
- `tests/test_gemini_wait_sidebar_thread_guard.py`
- `tests/test_routes_agent_v3_session_job_alignment.py`

辅助回归补跑：

- `tests/test_openclawbot_planning_task_plane_live_completion_gate.py`
- `tests/test_openclawbot_planning_task_plane_live_gate.py`

## 2. 这轮解决了什么问题

### 2.1 已修掉的核心风险

之前的 live 证据表明：

1. send 阶段已经升级到新的 Gemini thread
2. wait/export 阶段后来又 rebound 到旧 thread
3. 旧 thread 的无关答案被落盘并进入 planning checkpoint

这轮新增的 `thread guard` 解决的是：

1. 当 wait 已经绑定到具体 Gemini thread 时，不再允许静默切到另一个具体 thread
2. base `/app` 在单次 wait 调用内，一旦通过 sidebar/hint 选中具体 row，且 row 自带 `cid`，会优先用该 `cid` 生成预期 thread URL，再作为后续 guard 基准
3. 如果 row 没有 `cid`，则不会继承旧的 stale thread；会先 reset，再以 `after_click/after_goto` 真实拿到的 thread URL 重新锚定
4. `_open_row()` 里原来缺失 `nonlocal expected_conversation_url`，导致 debug 面看起来像已经锚到 row `cid`，实际外层 guard 变量仍会被当前页面 thread 漂白；这轮已修正
5. thread mismatch 现在直接 fail-closed，返回稳定错误码 `GeminiConversationThreadMismatch`

### 2.2 已修掉的 session surface 缺口

之前 `routes_agent_v3` 的 direct `kind=job` session refresh 会丢掉 `_job_snapshot()` 已经投影好的 repair payload，退回成裸 `check_status`。

这轮修复后：

1. direct `job` session refresh 会保留 snapshot 里的 `next_action`
2. `GeminiConversationThreadMismatch` 会在 public session 面上表现为：
   - `status=needs_followup`
   - `next_action.type=same_session_repair`

## 3. 验证结果

### 3.1 代码级回归

通过：

1. `python3 -m py_compile chatgpt_web_mcp/providers/gemini/wait.py chatgptrest/api/routes_agent_v3.py tests/test_gemini_wait_sidebar_thread_guard.py tests/test_gemini_wait_param_compat.py tests/test_gemini_wait_conversation_url_upgrade.py tests/test_routes_agent_v3_session_job_alignment.py`
2. `./.venv/bin/pytest -q tests/test_gemini_wait_sidebar_thread_guard.py tests/test_gemini_wait_param_compat.py tests/test_gemini_wait_conversation_url_upgrade.py tests/test_routes_agent_v3_session_job_alignment.py tests/test_openclawbot_planning_task_plane_live_completion_gate.py tests/test_openclawbot_planning_task_plane_live_gate.py`

其中新增的关键执行级覆盖是：

1. `selected row cid=A`
2. 点击后页面落到 `thread B`
3. `gemini_web_wait` 必须返回 `GeminiConversationThreadMismatch`
4. 不能把 `thread B` 的结果继续当成当前 wait 的合法 thread

### 3.2 live gate

当前最新 live artifact：

- `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260403_v1/report_v1.json`
- `docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260403_v1/report_v1.md`

最新 live gate 结果不是 completion verdict，而是更早的 bootstrap 失败：

1. `terminal_status=ask_failed`
2. 根因仍是 `OpenClaw dynamic replay harness ... TypeError: fetch failed`

所以这轮能成立的 live 口径是：

1. 现在没有新的 live 证据显示“旧 thread 脏答案又被静默完成”
2. 但因为 bootstrap 先失败了，这一轮也还没有拿到新的 end-to-end completion proof

## 4. 当前独立判断

### 4.1 可以明确成立的

1. `Gemini wait/export` 的 thread contamination 风险已经被代码级 fail-closed 收紧
2. public session surface 已经能把这类错误投成 `same_session_repair`
3. direct `job` session refresh 不再丢 repair payload
4. 这轮被真正打实的是 `selected row cid=A -> observed thread=B` 这个关键污染分支

### 4.2 还不能过度声称的

1. 还不能声称 live completion gate 已重新变绿
2. 还不能声称 `OpenClawBot -> live ask bootstrap` 这层已经恢复稳定
3. 还不能声称整个 `/app + conversation_hint` lane 已经全域 fail-closed；当前 `no-cid` 行选择仍是下一步要继续收紧的点

## 5. 下一步

下一步不应再扩新能力，仍然只做一件事：

1. 把 `OpenClaw dynamic replay harness fetch failed` 这一层拿下
2. 在新的 live bootstrap 通过后，再重跑 completion gate
3. 用新的 live evidence 确认：
   - 不再错答完成
   - session surface 确实表现为 `same_session_repair`
