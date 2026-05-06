# 2026-04-03 Gemini Wait Thread Guard And Session Repair Walkthrough v1

## 做了什么

这轮沿着 live evidence 往回追，只收真实 blocker，不扩 planning 面。

### 1. 收紧 Gemini wait

在 `chatgpt_web_mcp/providers/gemini/wait.py` 新增了：

1. `thread mismatch` fail-closed helper
2. 单次 wait 内的 base `/app` -> concrete thread lock
3. `sidebar row cid -> expected thread URL` 的优先锚定
4. `no cid` 时的 stale-anchor reset，再由 `after_click/after_goto` 重新锚定
5. 最终 result 出口上的 thread guard
6. 修掉 `_open_row()` 缺失 `nonlocal expected_conversation_url` 的作用域 bug，避免“debug 看起来锚对了、真实 guard 变量却没更新”

目标是阻断：

1. send 已经拿到新 thread
2. wait/export 又跳回旧 thread
3. 旧 thread 答案被当成当前任务答案

### 2. 收紧 public session projection

在 `chatgptrest/api/routes_agent_v3.py` 新增了：

1. `_error_requires_same_session_repair(...)`
2. `GeminiConversationThreadMismatch -> needs_followup + same_session_repair`
3. direct `kind=job` refresh 保留 snapshot 的 `next_action`

### 3. 补回归

新增/更新测试：

1. `tests/test_gemini_wait_param_compat.py`
2. `tests/test_gemini_wait_conversation_url_upgrade.py`
3. `tests/test_gemini_wait_sidebar_thread_guard.py`
4. `tests/test_routes_agent_v3_session_job_alignment.py`

并补跑：

1. `tests/test_openclawbot_planning_task_plane_live_completion_gate.py`
2. `tests/test_openclawbot_planning_task_plane_live_gate.py`

## 为什么这样改

因为这一轮真正的问题不是：

1. planning prompt 不够好
2. task_id/checkpoint 又要再扩

而是一个更底层、更危险的问题：

1. provider wait/export 可能把错误 thread 的答案写回当前任务

所以优先级必须是：

1. 先 fail-closed
2. 再把 public session surface 投成可修复状态
3. 最后再回到 live acceptance

## 当前状态

代码级回归已经全绿。

其中最关键的新覆盖不是纯 helper，而是执行级场景：

1. base `/app + conversation_hint`
2. sidebar title match 命中 row
3. row 自带 `cid=A`
4. click 后页面实际落到 `thread B`
5. wait 必须 fail-closed，而不是把 `B` 漂白成当前合法 thread

这里要收紧一句口径：

1. 现在被实证拿下的是 `cid` 可解析的关键污染分支
2. `no-cid` 行选择还没有做到全域 fail-closed，只是不会继承旧 stale thread

当前最新 live completion gate 仍未恢复到 completion verdict，因为：

1. `OpenClaw dynamic replay harness`
2. 在 bootstrap ask 阶段仍有 `fetch failed`

所以这轮的收口是：

1. 代码级 thread contamination 收紧已完成
2. live 入口上游还要继续修
