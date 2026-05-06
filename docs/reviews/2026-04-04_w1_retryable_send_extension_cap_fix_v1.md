# 2026-04-04 W1 retryable send extension cap fix v1

## 1. 这批修什么

这批修的是一个更接近 live 真阻塞的 job-store 语义问题：

同一个 send-phase job 的 `max_attempts` 扩容上限，之前实际上是按 `error_type` 分桶计数。

这意味着：

1. 第一次因为 `ToolCallError` 扩了一次
2. 下一次如果错误标签变成 `InfraError`
3. 同一个 job 还能再扩一次

结果就是 phase-1 live 链会被同一条 send 失败拖长，public session 继续长期显示 `running`。

## 2. 改动内容

### 2.1 job_store

在 [`job_store.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/core/job_store.py) 里：

1. `_retryable_send_extensions_used(...)` 不再按 `error_type` 过滤
2. `store_retryable_result(...)` 在判断 send extension limit 时，改为按同一 job 的总 send-extension 次数计数

也就是说：

- `CHATGPTREST_RETRYABLE_SEND_MAX_EXTENSIONS=1`
- 现在真的表示“同一个 job 总共只允许 1 次 send 扩容”
- 不再是“每种错误类型都能各扩一次”

### 2.2 测试

在 [`test_leases.py`](/vol1/1000/projects/ChatgptREST/tests/test_leases.py) 新增了跨错误类型测试：

- 先用 `ToolCallError` 触发第一次扩容
- 再用 `InfraError` 触发第二次 retryable result
- 现在应直接终态化为 `MaxAttemptsExceeded`
- 同时写出 `max_attempts_extension_skipped`，guard reason 为 `retryable_extension_limit_reached:1/1`

## 3. 为什么这批重要

这批不是“优化细节”，而是直接对应当前 live 现场：

1. 现场 job 已经出现 `ToolCallError -> InfraError` 切换
2. 同时出现了两次 `max_attempts_extended`
3. 这会把原本应更早失败收口的问题继续拉长

因此这批的意义是：

- 把 send retry 的上限重新变成可信的上限
- 避免同一条 send 链在错误标签漂移时继续扩命

## 4. 测试结果

这批实际跑过：

```bash
./.venv/bin/pytest -q tests/test_leases.py tests/test_worker_and_answer.py \
  -k 'retryable or gemini_send_phase_without_thread_evidence_stays_on_send or gemini_send_phase_with_response_evidence_requeues_wait or gemini_send_phase_with_pending_recovery_requeues_wait or gemini_send_phase_rebinds_to_latest_thread_url'
```

结果：全绿。

## 5. 当前判断

这批修复后，我的独立判断是：

1. live 链的 send-side churn 至少少掉了一条“错误标签切换继续扩命”的漏洞。
2. 这仍然不等于 `W1` 已完成。
3. 下一步必须用真实 OpenClawBot live gate 验证：
   - 是否更快终态化
   - 是否不再长时间卡成 `running`
   - 是否真正把 blocker 收窄到剩余的 terminal projection / provider path 问题
