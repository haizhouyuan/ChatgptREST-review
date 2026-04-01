# Google Workspace Surface Validation Pack v1

日期：2026-03-23

## 范围

本轮 validation pack 对 `google-workspace-surface-revival` 做 11 个检查，分成四层：

1. capability audit
2. alive-path probe
3. public agent northbound contract
4. service / report_graph / wrapper integration

实现文件：

- [google_workspace_surface_validation.py](/vol1/1000/projects/ChatgptREST/chatgptrest/eval/google_workspace_surface_validation.py)
- [run_google_workspace_surface_validation.py](/vol1/1000/projects/ChatgptREST/ops/run_google_workspace_surface_validation.py)
- [test_google_workspace_surface_validation.py](/vol1/1000/projects/ChatgptREST/tests/test_google_workspace_surface_validation.py)

产物：

- JSON report: [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/google_workspace_surface_validation_20260323/report_v1.json)
- Markdown report: [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/google_workspace_surface_validation_20260323/report_v1.md)

## 检查项

### 已通过

- `capability_audit`
- `rclone_remote_present`
- `public_agent_workspace_clarify`
- `public_agent_workspace_same_session_patch`
- `workspace_service_docs_gmail_chain`
- `workspace_service_drive_chain`
- `workspace_service_sheets_chain`
- `report_graph_workspace_outbox_contract`
- `cli_workspace_request_northbound`
- `skill_wrapper_workspace_request_northbound`

### 当前失败

- `workspace_auth_state`

失败原因不是 northbound contract 缺失，而是 live token probe 返回：

- `ok=false`
- `invalid_grant`

## 结果解释

这份 validation pack 当前证明了两件事：

1. Workspace northbound surface 已经收口
2. 当前 live OAuth token 还没有恢复

所以这轮结论不能写成“Google Workspace 全链 live ready”，只能写成：

- contract / service / outbox / public agent / wrapper：ready
- live OAuth state：not ready

## 验证命令

```bash
./.venv/bin/pytest -q \
  tests/test_workspace_contracts.py \
  tests/test_workspace_service.py \
  tests/test_workspace_outbox_handlers.py \
  tests/test_routes_agent_v3.py \
  tests/test_agent_mcp.py \
  tests/test_cli_improvements.py \
  tests/test_skill_chatgptrest_call.py \
  tests/test_check_public_mcp_client_configs.py \
  tests/test_google_workspace_surface_validation.py \
  tests/test_report_graph.py

python3 -m py_compile \
  chatgptrest/workspace/__init__.py \
  chatgptrest/workspace/contracts.py \
  chatgptrest/workspace/service.py \
  chatgptrest/workspace/outbox_handlers.py \
  chatgptrest/api/routes_agent_v3.py \
  chatgptrest/mcp/agent_mcp.py \
  chatgptrest/cli.py \
  skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  chatgptrest/eval/google_workspace_surface_validation.py \
  ops/run_google_workspace_surface_validation.py \
  ops/check_public_mcp_client_configs.py

PYTHONPATH=. ./.venv/bin/python ops/run_google_workspace_surface_validation.py
```
