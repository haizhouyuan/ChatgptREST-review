# 2026-04-04 W1 retryable send extension cap fix walkthrough v1

## 1. 触发点

在 live job `abefb47c1b7c462b827395ce9014e964` 的 DB 和 events 里，已经看到：

1. 同一 job 先因 `ToolCallError` 扩过一次 `max_attempts`
2. 后来又因 `InfraError` 再扩了一次

这直接说明：

当前 send-extension limit 不是按 job 总次数生效，而是被 `error_type` 切换绕过去了。

## 2. 代码动作

本批只改两个点：

1. `chatgptrest/core/job_store.py`
2. `tests/test_leases.py`

核心动作：

- `_retryable_send_extensions_used()` 改成只看同一 job 的 send-extension 总次数
- 不再按 `error_type` 分桶
- 新增跨错误类型 guard 测试

## 3. 验证动作

跑了：

```bash
./.venv/bin/pytest -q tests/test_leases.py tests/test_worker_and_answer.py \
  -k 'retryable or gemini_send_phase_without_thread_evidence_stays_on_send or gemini_send_phase_with_response_evidence_requeues_wait or gemini_send_phase_with_pending_recovery_requeues_wait or gemini_send_phase_rebinds_to_latest_thread_url'
```

结果通过。

## 4. 为什么这批先做

因为相比直接先改 session 投影，这个点更硬：

1. 它已经有真实 live evidence 支撑
2. 它是一个明确的语义 bug
3. 修掉后，live gate 的 terminal 行为会更接近真实上限

## 5. 下一步

提交后直接重跑 OpenClawBot live completion gate，看：

1. 同类 send-side churn 会不会更早失败收口
2. session 是否仍会长时间卡在 `running`
3. 如果仍 blocked，再决定先收 session projection 还是 provider terminalization
