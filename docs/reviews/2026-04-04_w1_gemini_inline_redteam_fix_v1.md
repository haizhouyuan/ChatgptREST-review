# 2026-04-04 W1 Gemini inline redteam fix v1

## 1. 触发原因

对 `ea6317a6` 的红队审核给出了 `reject`，核心 blocker 是：

1. 单小文本 inline lane 没有真实 size gate
2. 大文本 `.md` 也会被截断到前 12KB 后直接当成“inline 成功”
3. 同时清空 `file_paths`，导致 Drive upload 被完全跳过

这属于 silent truncation / data loss，不是文档问题。

## 2. 修复内容

在 [`gemini_web_mcp.py`](/vol1/1000/projects/ChatgptREST/chatgptrest/executors/gemini_web_mcp.py) 的 inline lane 里新增了真实文件大小检查：

1. 先 `path.stat().st_size`
2. 超过 `_gemini_single_inline_max_bytes()` 时直接 skip inline
3. 返回：
   - `single_text_inline_skipped=true`
   - `inline_skip_reason=file_too_large`
   - `inline_max_bytes`
   - `file_size_bytes`
4. 这时继续保留 `file_paths`，让后续 Drive upload 正常发生

## 3. 新增验证

在 [`test_gemini_drive_attach_urls.py`](/vol1/1000/projects/ChatgptREST/tests/test_gemini_drive_attach_urls.py) 补了一条红队反例测试：

- 构造 20KB 的 `.md`
- 验证不会 inline
- 验证会走 `_upload_files_to_gdrive`
- 验证 `tool_args.drive_files` 存在
- 验证 prompt 里没有 `Inlined Attachment Context`

## 4. 回归结果

这轮实际跑过：

```bash
./.venv/bin/pytest -q tests/test_gemini_drive_attach_urls.py tests/test_gemini_send_exception_retry.py tests/test_gemini_provider_timeout_budget.py tests/test_leases.py tests/test_worker_and_answer.py \
  -k 'gemini_single_small_text_attachment_is_inlined or gemini_large_single_text_attachment_falls_back_to_drive or retryable or gemini_send_phase_without_thread_evidence_stays_on_send or gemini_send_phase_with_response_evidence_requeues_wait or gemini_send_phase_with_pending_recovery_requeues_wait or gemini_send_phase_rebinds_to_latest_thread_url'
```

结果通过。

## 5. 当前判断

这次红队指出的是实 bug，我接受并已修掉。

当前判断是：

1. inline lane 现在才真正符合“small text”这个口径。
2. 这批之后，`contract_v1` 里的“small readable text file”描述才重新和实现一致。
3. 下一步可以继续重跑 live gate，而不是带着已知 silent truncation 缺陷往前跑。
