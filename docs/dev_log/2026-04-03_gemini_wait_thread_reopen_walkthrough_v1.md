# 2026-04-03 Gemini Wait Thread Reopen Walkthrough v1

## 做了什么

1. 收紧了 `gemini_web_wait`：
   - concrete thread 先 exact cid
   - 再 direct goto requested thread
   - exact cid 缺失时只允许 `body_probe_only`
   - 任何非请求 thread 都不能改写 `expected_conversation_url`
2. 补了 `Gemini 说/你说/显示思路` 等 anchor-only transcript 清洗。
3. 给“简短三条下一步”加了更轻的 `scenario pack` 路由。
4. 重新跑了 focused pytest。
5. 连续多轮重跑 `openclawbot planning task plane live completion gate`。

## 现场怎么变化的

1. 先前会拿到旧线程答案，导致 `answer_quality_ok` 假失败。
2. 后来变成 `requested cid` 缺失后的 fail-closed，不再错答。
3. 再后来 direct goto 已经能命中请求 thread，但 wait 期间页面还是会掉回 `/app`。

## 现在的结论

1. 本地 thread-selection 改善已经有代码和测试支撑。
2. 当前 live blocker 需要按 `Gemini live thread reopen / retention` 处理。
3. 这不是“继续调 prompt”能解决的问题。
