# Codex Maint Controller TodoList v1

日期：2026-03-24

## 目标

把分散的 Codex maintenance 能力收成一个统一、可升级、可审计的 maintenance control plane，并以 `sre.fix_request` lane/state 作为唯一 canonical run ledger。

## Todo

- [x] 把 `sre.fix_request` lane/state 固化为 canonical controller run ledger
- [x] 把 controller metadata 写进 lane manifest / decision history / report
- [x] 把 `taskpack/*` 落成 canonical lane artifacts 的标准化投影，而不是第二套 request/prompt 真相源
- [x] 把 incident 侧 `incidents/<id>/codex/*` 收成 mirror/pointer only，不再形成第二棵活跃 Codex 证据树
- [x] 把 maint incident analyze 路径接到 canonical lane controller
- [x] 把 maint fallback -> `repair.autofix` 路径接到 canonical lane controller
- [x] 把 maint runtime autofix escalation 路径接到 canonical lane controller，并复用 canonical decision
- [x] 把 recurring action preferences 从 maint memory 注入 escalation context
- [x] 增加 operator attach adapter，按 canonical lane attach/resume，而不是新增独立 controller 会话状态
- [x] 补一套独立 validation runner，把 controller 关键语义落成 JSON/Markdown 报告
- [x] 跑 compile + targeted pytest + validation runner
- [x] 补 completion / walkthrough / validation pack 文档

## 当前结论

`Codex Maint Controller` 已按蓝图 `v2` 的边界完成实现并验证通过。

边界：

- 这证明的是 lane-backed maintenance control plane 已完成
- 不是 live provider proof
- 不是 tmux/TUI operator UX 全量产品化
- `guardian` 仍是 wake/notify sidecar，不是 controller 主体
