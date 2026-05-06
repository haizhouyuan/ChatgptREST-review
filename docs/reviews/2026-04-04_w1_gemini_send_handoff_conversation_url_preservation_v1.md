# 2026-04-04 W1 Gemini send handoff conversation URL preservation v1

## 1. 这批改动解决什么

这批不是把 `W1` 做成，而是修一个更具体的 send-side 断点：

1. `gemini_web.ask` 在 success/error 两条路径上，之前都可能丢掉已经拿到的 `effective_conversation_url / best_effort conversation_url`
2. 这会直接削弱 `GeminiSendPendingRecovery` 的触发机会，也会让 planning checkpoint 拿不到任何可交接 URL
3. 同时，`gemini_web.ask` 的 error 路径里还存在一个 latent bug：`progress_step` 未初始化

## 2. 代码改动

本批只改了 1 个代码文件和 1 个测试文件：

1. [`chatgpt_web_mcp/providers/gemini/ask.py`](/vol1/1000/projects/ChatgptREST/chatgpt_web_mcp/providers/gemini/ask.py)
   - `gemini_web_ask(...)` 现在在 success 路径优先保留：
     - `best_effort conversation_url`
     - `effective_conversation_url`
     - `page.url`
   - error 路径也改成同样的回退顺序
   - 补上 `progress_step` 初始化与关键 send step 标记，避免 error 路径 `NameError`
2. [`tests/test_gemini_provider_timeout_budget.py`](/vol1/1000/projects/ChatgptREST/tests/test_gemini_provider_timeout_budget.py)
   - 新增 `gemini_web.ask` sent-timeout handoff test
   - 新增 `gemini_web.ask` success best-effort conversation_url test

## 3. 实际验证

这批实际跑过并通过：

```bash
./.venv/bin/pytest -q tests/test_gemini_provider_timeout_budget.py   -k 'ask_sent_timeout_uses_effective_conversation_url_for_wait_handoff or ask_success_prefers_best_effort_conversation_url or sent_timeout_returns_wait_handoff or initial_prompt'
```

以及更贴近 live 链的一轮：

```bash
./.venv/bin/pytest -q   tests/test_gemini_provider_timeout_budget.py   tests/test_gemini_idempotency_replay_recovery.py   tests/test_worker_auto_autofix_submit.py   tests/test_openclawbot_planning_task_plane_live_completion_gate.py   -k 'GeminiSendPendingRecovery or blank_gemini or sent_timeout or ask_success_prefers_best_effort_conversation_url or ask_sent_timeout_uses_effective_conversation_url_for_wait_handoff or live_completion_gate'
```

## 4. live evidence

真实 live rerun 产物：

- [v32 live report](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v32/report_v1.json)
- [v32 live report md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_v32/report_v1.md)
- [task checkpoint](/vol1/1000/projects/ChatgptREST/state/planning_tasks/tasks/pln_1b7f444c3490.json)

当前 live 结果仍然不是 `completed`：

- `terminal_status=needs_followup`
- `final_completion_ok=false`
- `answer_quality_ok=false`

但和前一批相比，这次有一个真实推进：

- planning task checkpoint 现在已经捕获：
  - `artifact_refs=["https://gemini.google.com/app"]`
  - `current_artifact_refs=["https://gemini.google.com/app"]`

这说明 send-side handoff URL preservation 已经进入 live task truth，而不是只存在于单测里。

## 5. 当前判断

我当前的独立判断是：

1. 这批修复是值得保留的，它补的是一个真实代码漏项。
2. 这批已经证明：`gemini_web.ask` 在 live fail-closed terminal 下，开始具备更好的 handoff URL 留存能力。
3. 但这批还不能证明 `W1` 已经过线，因为：
   - terminal 仍是 `needs_followup`
   - 最终答案仍然为空
4. 因此这批应被视为：
   - `W1` 的一条中间收敛修复
   - 不是 `W1 done`

## 6. 下一步

下一步继续做：

1. 检查 `same_session_repair` 是否已经真正消费这条保留下来的 base app URL
2. 继续压缩 `needs_followup` 到 `completed` 之间的最后断点
3. 再跑真实 live gate，直到拿到 `final_completion_ok=true`
