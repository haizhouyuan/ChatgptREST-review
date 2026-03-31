# Codex Maint Controller Completion Walkthrough v1

日期：2026-03-24

## 做了什么

1. 把 `sre.fix_request` lane 固化成 `Codex Maint Controller` 的唯一 canonical run ledger。
2. 在 lane manifest、decision history、report 里补了 controller metadata，并把 `taskpack/*` 限定为标准化投影。
3. 把 `maint_daemon` 的 incident analyze、fallback、runtime autofix escalation 全部改成通过 canonical lane controller 走。
4. 把 incident 侧 `codex/*` 收成 mirror/pointer only，避免 lane 和 incident 各写一套活跃 Codex 证据树。
5. 把 recurring action preferences 从 maint memory 注入 escalation context。
6. 增加了 [codex_maint_attach.py](/vol1/1000/projects/ChatgptREST/ops/codex_maint_attach.py)，让 operator attach/resume 以 canonical lane 为中心。
7. 补了独立 validation runner 和报告产物，避免只依赖散落的 pytest 结果。

## 为什么这样做

蓝图 `v2` 的关键约束是：

- 不新增第五套状态宇宙
- 不把 `taskpack/*` 做成第二套 request/prompt 真相源
- 不让 incident 侧 `codex/*` 和 lane 侧 `codex/*` 并行长成两棵活跃证据树

所以真正要做的是“统一 maintenance control plane”，不是“再造一个会拉起 Codex 的壳”。

## 怎么验证

验证包覆盖了 8 个关键语义：

1. compile targets 可正常导入/编译
2. canonical lane taskpack projection 成立
3. controller decision override 仍在 canonical lane 内路由 runtime fix
4. incident analyze 写回 mirror/pointer only
5. maint fallback / runtime fix escalation 都复用 canonical lane
6. recurring action memory preferences 可注入
7. operator attach adapter 可从 lane 或 incident pointer 解析目标
8. `repair.autofix` 既有 guardrails 未回归

结果：

- [report_v1.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/codex_maint_controller_validation_20260324/report_v1.json)
- [report_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/codex_maint_controller_validation_20260324/report_v1.md)

## 当前状态

`Codex Maint Controller` 已经可以作为后续 maintenance 自动升级和 operator attach 的正式实现基线。

当前仍明确不包含：

- `guardian` 作为 controller 主体
- tmux/TUI attach UX 产品化
- public northbound / provider 侧证明
