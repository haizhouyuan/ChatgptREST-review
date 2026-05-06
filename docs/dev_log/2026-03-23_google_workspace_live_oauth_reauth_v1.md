# Google Workspace Live OAuth Reauth v1

日期：2026-03-23

## 背景

`google-workspace-surface-revival` 收完后，唯一残留红点是 live OAuth token：

- `/home/yuanhaizhou/.openmind/google_token.json`
- silent load / refresh 返回 `invalid_grant`

这意味着：

- Workspace northbound contract / service / outbox / public agent surface 已 ready
- 但真实触达 Google API 的 live readiness 仍未恢复

## 本轮处理

新增运维脚本：

- [google_workspace_reauth_via_cdp.py](/vol1/1000/projects/ChatgptREST/ops/google_workspace_reauth_via_cdp.py)

脚本策略：

1. 使用现有 Desktop OAuth credentials
2. 通过已登录 Google 的 CDP Chrome 会话完成授权
3. 自动跨过 unverified warning
4. 自动勾选 consent summary 的全部 Workspace scopes
5. 回调到本地 `127.0.0.1` redirect 并写回新的 token JSON

## 结果

实际重授权已成功，token 已重新写入：

- `/home/yuanhaizhou/.openmind/google_token.json`

并且：

- [WorkspaceService.auth_state()](/vol1/1000/projects/ChatgptREST/chatgptrest/workspace/service.py) 现已返回 `ok=true`
- `run_google_workspace_surface_validation.py` 现已 `11/11` 通过

## 结论

这次不是 northbound 代码补丁，而是运行面恢复：

- `Workspace surface revival`: 继续成立
- `Workspace live OAuth readiness`: 已恢复

