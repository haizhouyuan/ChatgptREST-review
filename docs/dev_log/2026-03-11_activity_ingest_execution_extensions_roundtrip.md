# 2026-03-11 activity ingest execution extensions roundtrip

## Why

主线刚把 execution-layer extension 字段保留进 normalized identity view：

- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

但这还只证明了 `extract_identity_fields()` 支持这些字段。

还需要确认它们经过：

`ActivityIngestService.ingest_activity_event() -> canonical episode.source_ext`

这条链时不会丢失。

## What changed

文件：

- `tests/test_activity_ingest.py`

新增一个 roundtrip test：

- 构造 `task.completed` activity payload
- 在 `data` 中携带上述 execution extensions
- 验证 canonical episode `source_ext` 中仍然保留它们

## Result

这轮不改 runtime 代码，只补 ingest 链路回归。

意义是：

- 主线现在不只是“函数层支持 extension”
- 而是“canonical activity ingest 也确实保留 extension”

这样 `#115` 那条 contract 线后续给出的 adapter mapping，
在进入主线 runtime 时至少不会先被当前 ingest 链路吞掉。
