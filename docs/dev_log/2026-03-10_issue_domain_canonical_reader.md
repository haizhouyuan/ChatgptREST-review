# 2026-03-10 Issue-domain Canonical Reader

## 本次目标

只做 `issue_domain` 的 canonical reader：

- 真实读取 canonical plane
- 只读 `canonical_objects` + `projection_targets`
- 只接 `graph` + `ledger_ref`
- 不改 ledger 写入
- 不改 canonical ingest
- 不扩其它 domain

## 代码改动

### 新增

- `chatgptrest/core/issue_canonical.py`
  - 只读 canonical sqlite reader
  - query/export adapter
  - 只消费 `issue_domain`
  - 只暴露 `graph` / `ledger_ref`

- `tests/test_issue_canonical_api.py`
  - canonical object 存在
  - reader 能读到
  - query/export 返回 `ledger_ref` / `graph` projection
  - 旧 `/v1/issues/graph/query` 路径不回归

### 修改

- `chatgptrest/api/routes_issues.py`
  - 新增：
    - `POST /v1/issues/canonical/query`
    - `GET /v1/issues/canonical/export`

- `chatgptrest/api/schemas.py`
  - 新增 canonical query/export response model

## Authority 边界

- authoritative source 仍然是 `state/jobdb.sqlite3` 里的 issue ledger
- canonical 只是统一读取面
- `ledger_ref` 只是指出 authoritative row 在哪里
- `graph` 仍然是 derived projection，不反写 ledger

## 配置

- 新增只读环境变量：
  - `CHATGPTREST_CANONICAL_DB_PATH`

如果未配置且默认候选路径不可读：

- `/v1/issues/canonical/query`
- `/v1/issues/canonical/export`

会返回 `503 canonical issue plane not configured`

## 测试

通过：

- `python3 -m py_compile ...`
- `./.venv/bin/pytest -q tests/test_issue_canonical_api.py tests/test_issue_graph_api.py tests/test_issue_ledger_api.py tests/test_export_issue_views.py`

仓库全量 `pytest -q` 未完全绿，当前确认的现存红测：

- `tests/test_leases.py::test_retryable_qwen_cdp_limit_becomes_needs_followup`
  - 当前主机默认 `CHATGPTREST_QWEN_ENABLED=0`
  - 单测假设 `qwen_web.ask` 可创建 job

- `tests/test_rescue_followup_guard.py::test_rescue_followup_does_not_shortcircuit_when_parent_already_completed`
  - 与本次 issue canonical reader 无直接代码耦合
  - 当前行为是 follow-up 在 send 后保持 `in_progress`

## 结论

这次已经把 `issue_domain` 接成了第一条真实 canonical consumer。

范围内完成的是：

- read-only canonical reader
- minimal query/export API
- integration tests

没有做的是：

- evidence plane
- memory_hot
- codex_history trace graph
- canonical schema 重做
