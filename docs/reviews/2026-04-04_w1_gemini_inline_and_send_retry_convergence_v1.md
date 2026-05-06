# 2026-04-04 W1 Gemini inline and send retry convergence v1

## 1. 这批改动解决什么

这批不是宣布 `W1` 完成，而是收掉当前 Gemini send 链上两个明确的问题：

1. 单个小文本附件不该总是走 Drive attach。
2. `GeminiWebMcpExecutor` 外层 send exception retry 不该把 `SSE stream timeout / deadline exceeded` 这类超时继续当成可重试异常反复拖长。

## 2. 代码改动

本批只收了 3 个受控改动面：

1. 在 [`gemini_web_mcp.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/executors/gemini_web_mcp.py) 增加 `_is_retryable_gemini_send_exception(...)`
2. 在 [`gemini_web_mcp.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/executors/gemini_web_mcp.py) 增加单文件小文本 inline lane：
   - `_gemini_single_inline_max_bytes()`
   - `_maybe_inline_single_text_attachment(...)`
3. 在 send exception 分支只对明显 transport-level 拒连类异常做外层 retry，不再对 deadline-exceeded 类异常继续外层重试

这批明确没有带入当前 worktree 里其它与 `repo_context_hint / github_repo` 相关的脏改动。

## 3. 为什么这样收

### 3.1 单小文本附件 inline

当前 live OpenClawBot planning 完成链里，会议材料经常是单个小文本或转写片段。

如果这类输入还强制走 Drive attach：

1. 成本高
2. 速度慢
3. 更容易把 live 链的失败面拖到附件上传和 UI attach 路径

因此 phase-1 先做一个更窄的策略：

1. 只在 `exactly one current file path + exactly one original file path`
2. 非 `deep_research`
3. 文件可安全读取为小文本

时，把内容直接 inline 到问题体里，并把 `uploaded_count=0` 和 `single_text_inlined=true` 写进 attachment preprocess meta。

### 3.2 send exception retry 收窄

之前 executor 外层 retry 对 exception 太宽，会把：

- `McpHttpError: SSE stream timeout (deadline exceeded)`

继续当成 send retry 候选。这会带来两个问题：

1. 单次 send 会拖长
2. live evidence 更难分辨到底是 transport 瞬断，还是 provider path 本身已经超时

本批把外层 retry 收窄成：

1. `connection refused`
2. `ECONNREFUSED`
3. `transport error`

这类更接近瞬时连接问题的异常才外层 retry。

## 4. 测试结果

这批实际跑过并通过：

```bash
./.venv/bin/pytest -q \
  tests/test_gemini_send_exception_retry.py \
  tests/test_gemini_drive_attach_urls.py \
  tests/test_gemini_provider_timeout_budget.py \
  tests/test_openclawbot_planning_task_plane_live_completion_gate.py \
  tests/test_run_openclawbot_planning_task_plane_live_completion_gate.py
```

结果：

1. 单小文本附件 inline lane 有单测证明
2. `deadline exceeded` 不再触发 executor 外层重试
3. `connection refused` 这类 transport 异常仍保留外层 retry

## 5. 对 live 链的意义

这批改动的价值，不是“live 已全绿”，而是把 live blocker 再往前推进了一层：

1. 当前问题已经不再停留在“Drive attach 本身”
2. 现场最新 evidence 已推进到：
   - `ask_failed -> probe_failed`
   - session 仍在 `running`
   - job 在 send phase 反复 `cooldown`
   - 底层错误是 `ToolCallError / SSE stream timeout (deadline exceeded)`

也就是说，当前剩余主问题已经更聚焦到：

1. Gemini send phase timeout/churn
2. send-phase failure 如何更快终态化
3. live gate timeout 与 session terminal projection 的一致性

## 6. 当前判断

这批应当视为 `W1` 的一次收敛性修复，而不是完成标志。

我当前的独立判断是：

1. 单小文本材料 inline lane 值得保留，它符合 phase-1 真实材料结构。
2. send exception retry 必须继续维持窄边界，不能再回到“大异常一律重试”。
3. `W1` 仍未完成，下一批应继续打 live send timeout/churn，而不是扩新 surface。

## 7. 下一步

下一步继续做：

1. 查 live send phase 的 repeated cooldown / timeout churn
2. 查 session 为什么在 terminal wait deadline 内仍保持 `running`
3. 再跑真实 OpenClawBot live completion gate，直到 W1 真正过线
