# 2026-03-24 Gemini Pending Send Recovery And Import Lane Fix Walkthrough v1

## 做了什么

这轮没有继续堆上层 deliberation / dual-review 功能，而是回到底层 Gemini 可用性做了两件事：

1. 把 Gemini stale idempotency replay 从“空壳 in-progress”改成可 handoff 到 `wait` 的 pending recovery。
2. 把 Gemini repo import lane 从 generic runtime 故障里剥出来，避免 `repair.autofix` 自己制造噪音。

## 为什么这样改

此前失败链路里，真正的问题不是 retry 次数不够，而是：

- prompt 已经标记 `sent=true`
- 但 send 阶段没有稳定 thread URL
- replay 再回来时也不给 wait 一个可恢复信号

这样系统就会在 send 里重复冷却，最后把长任务误收口成 `MaxAttemptsExceeded`。

repo import 那条则是另一类问题：它不是 driver/chrome 真坏了，而是 Gemini UI 的 import lane 不可用。对这种问题继续 restart，只会污染 repair history。

## 结果

修复后：

- Gemini ask/pro/pro_thinking/pro_deep_think 遇到 sent-but-no-thread replay，会直接进入 wait/sidebar recovery
- send worker 会把这类任务 requeue 到 `wait`
- repo import unavailable 会被明确分类成 `GeminiImportCodeUnavailable`
- SRE fast-path 不再把它送去 runtime autofix

## 我对当前状态的判断

这次修复后，Gemini 的可用性基线比之前明显更合理：

- 长任务不会再因为 stale replay 而在 send 阶段白白烧 attempts
- autofix 也少了一条明显错误的修复路径

但还不能把 GeminiDT 说成“完全收口”。下一步仍然应该回到真实 GeminiDT 评审任务，验证：

1. 文本 `deep_think` 能否稳定进入 wait 并最终拿到答案
2. repo import lane 如果仍不可用，系统是否会安静失败并引导切 transport，而不是继续自激

## 相关文件

- `chatgpt_web_mcp/providers/gemini/ask.py`
- `chatgpt_web_mcp/providers/gemini/core.py`
- `chatgpt_web_mcp/providers/gemini_helpers.py`
- `chatgptrest/executors/sre.py`
- `tests/test_gemini_idempotency_replay_recovery.py`
- `tests/test_gemini_wait_conversation_hint.py`
- `tests/test_worker_and_answer.py`
- `tests/test_gemini_mode_selector_resilience.py`
- `tests/test_sre_fix_request.py`
