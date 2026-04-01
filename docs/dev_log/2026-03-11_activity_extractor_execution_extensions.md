# 2026-03-11 activity extractor execution extensions

## Why

主线 runtime 这边已经把 execution-layer extension 保留进了 activity
identity view：

- `lane_id`
- `role_id`
- `adapter_id`
- `profile_id`
- `executor_kind`

如果 review/candidate 平面的 `activity_extractor` 还不把这些字段写进
atom applicability，那么主线虽然在 live ingest 里保住了它们，
一到 extractor 又会丢一遍。

## What changed

文件：

- `chatgptrest/evomap/knowledge/extractors/activity_extractor.py`
- `tests/test_activity_extractor.py`

调整：

- `_closeout_to_atom()` applicability 透传上述 execution extensions
- `_commit_to_atom()` applicability 透传上述 execution extensions
- 样例 closeout / commit 事件补上 execution extension 字段
- 断言 extractor 产出的 candidate applicability 中保留这些字段

## Boundary

这轮不改：

- runtime ingest
- EventBus / TraceEvent
- promotion status
- retrieval / runtime visibility gate

只做 review/candidate 平面的 metadata 保真。
