# 2026-03-09 Issue Graph Closed Loop Implementation

## Goal

把 ChatgptREST 的 issue 体系从“有 ledger 和 open issue list”补成完整闭环：

- authoritative ledger
- structured verification / usage evidence
- derived issue graph snapshot
- graph query API
- MCP graph/evidence tools
- guardian close rule with persisted evidence

## What Changed

### 1. Authoritative ledger expanded

- `client_issue_verifications`
- `client_issue_usage_evidence`

对应代码：

- `chatgptrest/core/db.py`
- `chatgptrest/core/client_issues.py`

结果：

- `mitigated` 不再只是状态变化，可以挂结构化 `Verification`
- `closed` 不再只靠 close metadata，可以挂结构化 `UsageEvidence`

### 2. Issue graph projection added

新增：

- `chatgptrest/core/issue_graph.py`
- `ops/export_issue_graph.py`
- `ops/systemd/chatgptrest-issue-graph-export.service`
- `ops/systemd/chatgptrest-issue-graph-export.timer`

导出产物：

- `artifacts/monitor/issue_graph/latest.json`
- `artifacts/monitor/issue_graph/latest.md`

图节点当前覆盖：

- `Issue`
- `Family`
- `Verification`
- `UsageEvidence`
- `Job`
- `Incident`
- `Document`

补充：

- `issue_graph.py` 现在会从旧的 `issue_status_updated` 事件里回灌历史 `mitigated/closed` 证据
- 对 `follow-up / followup / follow up` 这类词形漂移做了正规化匹配
- 这样历史单不需要重新写库，也能在图里长出 `Verification / UsageEvidence`

### 3. API contract completed

新增接口：

- `POST /v1/issues/{issue_id}/verification`
- `GET /v1/issues/{issue_id}/verification`
- `POST /v1/issues/{issue_id}/usage`
- `GET /v1/issues/{issue_id}/usage`
- `POST /v1/issues/graph/query`
- `GET /v1/issues/graph/snapshot`

对应代码：

- `chatgptrest/api/schemas.py`
- `chatgptrest/api/routes_issues.py`

### 4. Guardian close loop persisted

`openclaw_guardian_run.py` 现在不再只把 3 次成功放进 close metadata：

- quiet-window auto-mitigate 会附带 `verification`
- auto-close 会附带 `qualifying_successes[]`
- `update_issue_status()` 会把这些结构化数据写进 ledger

### 5. MCP tools completed

新增：

- `chatgptrest_issue_record_verification`
- `chatgptrest_issue_list_verifications`
- `chatgptrest_issue_record_usage`
- `chatgptrest_issue_list_usage`
- `chatgptrest_issue_graph_query`

对应代码：

- `chatgptrest/mcp/server.py`

## Validation

回归：

- `tests/test_issue_graph_api.py`
- `tests/test_issue_ledger_api.py`
- `tests/test_export_issue_views.py`
- `tests/test_openclaw_guardian_issue_sweep.py`
- `tests/test_mcp_issue_tools.py`

编译：

- `py_compile` on core/api/ops/test touched files

Live：

- API / MCP / `chatgptrest-issue-graph-export.timer` 已重启并生效
- live smoke issue：`iss_cf1a716cf9aa471283452792452b6aa4`
  - `report -> mitigated -> closed`
  - `verification count = 1`
  - `usage evidence count = 3`
  - `graph query` 返回 `issue/family/verification/usage/job/incident`
- 导出快照：
  - `artifacts/monitor/issue_graph/latest.json`
  - `artifacts/monitor/issue_graph/latest.md`
  - 当前 live summary 已包含历史回灌后的 `verification_count=127`、`usage_evidence_count=64`

## Commits

- `4a69055` `feat(issues): persist verification and issue graph state`
- `10b14aa` `feat(mcp): expose issue graph and evidence tools`
- `a6c6577` `feat(issues): harvest legacy graph evidence and normalize query`

## Notes

- authoritative state 仍然在 ledger，不在 graph
- graph 是 derived projection，可重建、可导出、可查询
- 这轮没有把 GitNexus symbol/process 关系并入 issue graph；代码图仍保持独立输入层
