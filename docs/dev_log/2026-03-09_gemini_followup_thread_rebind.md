# 2026-03-09 Gemini Deep Think Follow-up Thread Rebind

## 背景

Codex 会话里再次暴露 Gemini Deep Think / Deep Research follow-up 不能在同一逻辑会话里继续的问题。表面症状是：

- client 明明传了 `parent_job_id`
- send 阶段也拿到了新的 Gemini thread URL
- 但 job 最后还是掉成 `needs_followup`
- `result.json` 和 DB 里的 `conversation_url` 还停在旧线程，wait 后续继续盯旧 URL

## 根因

这次确认是两个状态边界同时出错：

1. `chatgptrest/core/job_store.py:set_conversation_url`
   - 对 Gemini follow-up 场景里“旧 thread URL -> 新 thread URL”的变化仍按 `conversation_url_conflict` 处理
   - 结果是新的 live thread URL 没有成为 job row 真相源

2. `chatgptrest/worker/worker.py:_run_once`
   - 多处仍然优先使用旧的 `job.conversation_url`
   - 即便 executor meta 已经返回了新的 thread URL，也可能继续拿旧 URL 去 export / issue report / autofix / wait 关联

3. `chatgptrest/executors/gemini_web_mcp.py:GeminiWebMcpExecutor._run_ask`
   - 之前只把 `send_without_new_response_start` 这一类 send-stage follow-up 接入 auto-followup
   - 新的 live 证据表明，Gemini 还会直接返回：
     - 新 thread URL
     - 研究方案页正文
     - `status=needs_followup`
   - 这个 send-stage `needs_followup + plan stub` 分支此前没有进入 auto-followup

## 代码修复

### 1. 允许 Gemini thread rebinding

在 `set_conversation_url()` 中新增 Gemini 线程 rebinding 语义：

- 条件：
  - `job.kind == "gemini_web.ask"`
  - `existing_url` 是 Gemini thread URL
  - `new_url` 也是 Gemini thread URL
- 动作：
  - 允许把 job row 的 `conversation_url/conversation_id` 迁移到新的 thread URL
  - 记录事件 `conversation_url_rebound`

这样做不是“放宽冲突保护”，而是把 Gemini follow-up 的真实线程迁移写实到存储层。

### 2. worker 以最新 executor URL 为准

把 `_run_once()` 中多个 `conversation_url` 选择顺序从：

- `job.conversation_url or conversation_url`

改成：

- `conversation_url or job.conversation_url`

保证 executor 本轮刚拿到的新 thread URL 优先于旧 job 快照。

### 3. send-stage 研究方案页也自动推进

在 `GeminiWebMcpExecutor._run_ask()` 中新增：

- 对 send 阶段返回的 `status=needs_followup`
- 如果 `answer` 经 `_classify_deep_research_answer()` 仍判为研究方案页
- 且当前是 `deep_research_effective`

则自动走一次同线程 `gemini_web_deep_research` follow-up，再继续 wait。

## 测试

新增/更新的回归覆盖：

- `tests/test_conversation_url_conflict.py`
  - `test_set_conversation_url_rebinds_gemini_thread_for_in_progress_followup`
- `tests/test_worker_and_answer.py`
  - `test_gemini_send_phase_rebinds_to_latest_thread_url`
- `tests/test_gemini_followup_wait_guard.py`
  - `test_gemini_send_plan_stub_auto_confirms_once`

执行通过：

```bash
PYTHONPATH=. ./.venv/bin/pytest -q \
  tests/test_gemini_followup_wait_guard.py \
  tests/test_conversation_url_conflict.py \
  tests/test_worker_and_answer.py -k 'gemini or conversation_url or send_phase_requeues_wait'
```

## Live 验证

### 旧代码失败证据

job `e2f1e6d24d334841b482e34656464c9f`（旧 generic send worker `164223`）：

- `conversation_url_conflict`
- 新 URL: `https://gemini.google.com/app/d073242fd0978a79`
- `result.json` 仍写回旧 URL: `https://gemini.google.com/app/37c4d915383e2fd2`
- 终态：`needs_followup`

这条就是根因的直接证据。

### 新代码成功证据

job `2d182c9b9ae1477e855e82d11f040a9e`（新 Gemini send worker `236499`）：

- `conversation_url_rebound`
- 旧 URL: `https://gemini.google.com/app/37c4d915383e2fd2`
- 新 URL: `https://gemini.google.com/app/f83cf6e476b0b469`
- DB job row 已迁移到新 URL
- send 终态不再卡在旧线程，而是正常 `phase_changed -> wait_requeued`

这说明“同一逻辑会话 follow-up 被旧线程绑死”的根因已经修掉。

## 客户端契约更新

为减少冷启动 Codex 再次踩坑，同步更新：

- `docs/codex_fresh_client_quickstart.md`
- `skills-src/chatgptrest-call/SKILL.md`

新的明确约定：

- Gemini follow-up 优先传 `parent_job_id`
- 不要把旧 `conversation_url` 当成唯一真相源
- 不要手工补发“开始研究 / OK”；服务端会对研究方案页自动推进一次

## 仍需继续观察

- wait 阶段最终完成率仍受队列吞吐和网页稳定性影响，需要继续观察新 `conversation_url_rebound` 路径是否还有后续 `needs_followup`
- 历史 ledger 里的旧 Gemini DR issue 需要按新 live 证据逐步收口，不能用旧失败 job 继续代表当前基线
