# Google Workspace Surface Revival Walkthrough v2

日期：2026-03-23

## 为什么还需要 v2

[v1](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-23_google_workspace_surface_revival_completion_v1.md) 收的是产品面：

- contract
- service
- outbox
- public surface

但当时 live token 已坏，`workspace_auth_state` 是红的。

所以 v2 的目的不是改设计，而是把运行面补齐。

## 这次真正修的是什么

不是：

- 重写 Workspace adapter
- 替换 `rclone`
- 修改 northbound contract

而是：

- 用已有 Google 登录 Chrome 会话重新完成 Desktop OAuth
- 把有效 token 写回 `~/.openmind/google_token.json`

## 为什么用 CDP reauth

当前环境里：

- Chrome 已登录 Google 账号
- OAuth client / scopes 都是正确的
- 问题只是 token refresh 已经 `invalid_grant`

所以最稳的修法是：

1. 复用现有浏览器登录态
2. 自动过 warning / consent
3. 本地回调完成 token exchange

## 结果

这次之后，Workspace 这条线不再只是“产品面已 ready，live auth 未 ready”，而是：

- 产品面 ready
- live auth ready

因此现在可以把 Google Workspace 视为：

- 一个已完成的 northbound task surface
- 而不是仍挂着红色运维 residual 的半完成项

