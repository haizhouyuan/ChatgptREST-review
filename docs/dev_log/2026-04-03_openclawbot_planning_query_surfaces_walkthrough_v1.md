# 2026-04-03 OpenClawBot Planning Query Surfaces Walkthrough v1

## 做了什么

1. 给 `openmind-advisor` plugin 增加了 `task_get/task_list/session_get` 的摘要化 payload。
2. 给 `session_get` 增加了 runtime session 限制和 cross-session fail-closed。
3. 给 planning task GET/list 的 read-path refresh 加了：
   - no-op skip
   - refresh failure fallback
4. 补了 `cancelled` 映射。
5. 补了 runner 非绿退出与隔离输出目录测试。

## 为什么这么做

因为前一轮红队指出的两个问题是实锤：

1. plugin 查询面返回过宽
2. planning task GET/list 的 refresh 会把“读”做成“脆弱的写”

这两条都属于继续开发前必须先收的边界问题。

## 这次不做什么

1. 不把 `/v3/agent/session/{session_id}` 后端 surface 一次性重构掉。
2. 不在这批里把 read refresh 改成全新机制。
3. 不把 live bootstrap `fetch failed` 问题假装修好了。

## 当前结果

本地回归已绿；plugin/query surface 收紧成立；live completion gate 现在至少会如实 fail-closed。
