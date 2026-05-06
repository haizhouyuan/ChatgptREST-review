# 2026-04-13 ChatGPT Pro Active Finalization Retry Budget Fix v1

## 现象

在 `chatgpt_web.ask + preset=pro_extended` 的长思考场景里，worker 会遇到一种特殊 export 形态：

- assistant 已经给出短 `commentary` preamble
- export 里还有一个 `role=tool` 的 `in_progress` 节点
- 该节点 metadata 含：
  - `is_finalizing=true`
  - `pro_progress=<number>`

这说明模型实际上还在 finalize，而不是浏览器/UI 真正异常。

但是旧逻辑在 wait-phase 里没有识别这类 active finalization 信号：

- 每个 wait slice 结束都走 `_store_browser_retry_or_fail_closed(...)`
- 于是被记成 `browser_retry_scheduled`
- 长思考会话会白白消耗 browser retry budget
- 最终可能以 `WebRetryBudgetExceeded` fail-close，即使模型并没有真的卡死

## 根因

worker 只看到了：

- wait slice 结束时仍然没有 final answer text

却没有把 export 里的以下信号纳入 retry budget 判定：

- `tool` 节点仍在 `in_progress`
- `metadata.is_finalizing=true`
- `metadata.pro_progress` 持续存在

## 修复

1. 在 `chatgptrest/worker/worker.py` 新增：
   - `_conversation_export_active_finalization_details(...)`

2. wait-phase export 解析时，把 active finalization 信号写回 `result.meta`：
   - `export_active_finalization=true`
   - `export_active_finalization_details={...}`

3. 在 worker 的 wait requeue 路径上加分叉：
   - 如果命中 `export_active_finalization`
   - 则：
     - 记录 `wait_active_finalization_observed`
     - 直接 `release_for_wait(...)`
     - 不再写 `browser_retry_scheduled`
     - 不再消耗 browser retry budget

## 验证

新增测试：

- `test_wait_phase_active_finalization_requeues_without_browser_retry_budget`

验证点：

- job 继续保持 `status=in_progress, phase=wait`
- 事件里有：
  - `wait_requeued`
  - `wait_active_finalization_observed`
- 事件里没有：
  - `browser_retry_scheduled`
  - `browser_retry_budget_exceeded`

## 影响

这个修复不改变真正的 UI 异常/冷却/阻塞处理。

它只修正一类误判：

- `Pro` 长思考仍在 finalize
- 但旧逻辑把它当成浏览器重试

因此这是一个 **retry budget accounting fix**，不是放宽真正异常的 fail-close 策略。
