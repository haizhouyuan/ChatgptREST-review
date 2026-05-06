# 2026-04-04 W1 Gemini inline and send retry convergence walkthrough v1

## 1. 背景

在上一批 live evidence 里，OpenClawBot planning completion 已经从早先的 `attach_drive_files` 失败推进到了新的阻塞点：

1. session 长时间保持 `running`
2. job 在 send phase 反复 `cooldown`
3. `last_error_type=ToolCallError`
4. `last_error` 指向 `McpHttpError: SSE stream timeout (deadline exceeded)`

因此这批不再扩新功能，而是收两件事：

1. 单小文本附件走 inline shortcut
2. send exception retry 收窄

## 2. 实际动作

### 2.1 交互式暂存清理范围

先在已有 shell 会话里用 `git add -p` 只暂存目标 hunks：

1. `chatgptrest/executors/gemini_web_mcp.py`
2. `tests/test_gemini_drive_attach_urls.py`
3. `tests/test_gemini_send_exception_retry.py`

明确排除：

1. `chatgpt_web_mcp/providers/gemini/ask.py` 里的 debug instrumentation
2. `repo_context_hint / github_repo` 一类当前 worktree 中的无关脏改动
3. `tests/test_gemini_provider_timeout_budget.py` 里的临时调试断言

### 2.2 代码面

落地了：

1. `_is_retryable_gemini_send_exception(...)`
2. `_gemini_single_inline_max_bytes()`
3. `_maybe_inline_single_text_attachment(...)`
4. `_run_ask(...)` 中对 inline lane 的接入
5. send exception 分支的收窄 retry 条件

### 2.3 测试

跑了：

```bash
./.venv/bin/pytest -q \
  tests/test_gemini_send_exception_retry.py \
  tests/test_gemini_drive_attach_urls.py \
  tests/test_gemini_provider_timeout_budget.py \
  tests/test_openclawbot_planning_task_plane_live_completion_gate.py \
  tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py
```

结果全绿。

## 3. 为什么不把更多东西一并塞进来

因为当前 worktree 还有其它与 Gemini repo context 相关的脏改动，那不是这批的主问题。

这批如果把它们一起提交，会导致：

1. diff 目标变脏
2. 红队很难判断“这批到底修了什么”
3. live blocker 定位继续发散

所以这批坚持只收：

1. single-text inline
2. exception retry narrowing

## 4. 当前结果

结果不是 `W1 done`，而是：

1. 附件预处理策略更符合 phase-1 真实材料
2. send timeout/churn 证据链更干净
3. 后续 live 排障面进一步收窄

## 5. 后续接续点

下一批继续从 `W1` 主 blocker 往下打：

1. live send timeout/churn
2. terminal wait timeout 下 session 仍 running 的终态投影问题
3. 直到真实 OpenClawBot live completion gate 全绿
