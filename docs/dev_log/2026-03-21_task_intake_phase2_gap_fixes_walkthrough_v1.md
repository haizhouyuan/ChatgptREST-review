# 2026-03-21 Task Intake Phase2 Gap Fixes Walkthrough v1

## 1. 这轮为什么没有只改文档

review 提出的两个点都指向同一个问题：

- canonical intake 还没有完全掌握自己的语义边界

如果这时只把阶段文档改软，Phase 3 再往上搭 `planning` pack，后面还会继续在入口层漏语义。

所以这轮选择直接补代码，而不是只降级结论。

## 2. 修法取舍

### 2.1 为什么不是只给 plugin 加 `planning`

因为那样会把问题继续留在 adapter：

- 今天是 `planning`
- 明天还会有别的 hint

正确修法必须是：

- canonical builder 学会 `planning`
- adapter 不再默认替 server 写死 `general`

### 2.2 为什么 attachments 不在 route 层单点修

如果只在 `/v2/advisor/advise` 里把 `raw_task_intake.attachments` 捞出来，
那别的调用 `build_task_intake_spec(...)` 的入口还是会继续丢。

所以 attachments merge 必须落在 builder。

## 3. 结果

修完之后，`Phase 2` 剩下的就只是真正的阶段边界问题：

- Feishu 还没迁路由
- `/v1/advisor/advise` 还活着
- mixed MCP/CLI callers 还没完全 retired

这些都不再是 payload semantics 漏损，而是后续迁移/收敛问题。
