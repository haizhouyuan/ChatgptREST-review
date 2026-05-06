# 2026-03-07 wait worker `not_before` 热循环修复

## 现象
- `chatgptrest-worker-wait.service` 常驻约 `2.2G`~`2.4G`
- 主进程 RSS 实际很小，cgroup 内存主要是 `file` cache
- 同一条 `gemini_web.ask` wait job 被反复 claim/requeue

## 根因
- `chatgptrest/executors/base.py` 在 `conversation_url` 缺失时返回：
  - `status=in_progress`
  - `retry_after_seconds=30`
  - `not_before=time.monotonic() + 30`
- 但 `not_before` 在 job store 中按 wall-clock epoch 秒使用，并用 `time.time()` 比较。
- 单调时钟值被写进 SQLite 后会变成一个很小的数字，wait worker 会把该 job 视为“立刻可重试”，形成热循环。

## 修复
1. `chatgptrest/executors/base.py`
   - 把 `not_before` 改为 `time.time() + wait_seconds`
2. `chatgptrest/worker/worker.py`
   - 新增 `_coerce_retry_not_before()`
   - 对 wait / cooldown / blocked / needs_followup / retryable error 的 `not_before` 做统一校验
   - 小于 `1_000_000_000` 的值按无效 wall-clock 处理，回退到 `time.time() + retry_after`
3. 运行态修复
   - 将数据库中已写坏的 wait job `not_before` 改到合法 epoch
   - 重启 `chatgptrest-worker-wait.service`

## 验证
- 针对性测试：
  - `tests/test_gemini_wait_transient_handling.py`
  - `tests/test_worker_not_before_normalization.py`
- 运行态：
  - 非法 `not_before` wait job 数量已归零
  - `chatgptrest-worker-wait.service` 重启后内存恢复到 MB 级

## 备注
- 这次问题不是 Python 堆泄漏，而是 wait 热循环触发的 cgroup 文件缓存膨胀。
