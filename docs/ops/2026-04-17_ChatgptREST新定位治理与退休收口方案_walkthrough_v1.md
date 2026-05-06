---
title: ChatgptREST新定位治理与退休收口方案 Walkthrough
status: completed
updated: 2026-04-17
owner: Codex
---

# ChatgptREST新定位治理与退休收口方案 Walkthrough

## 做了什么

1. 复核了 `AGENTS.md`、`docs/contract_v1.md`、`docs/README.md` 与 `docs/ops/*` 的 current guidance。
2. 复核了 public MCP、旧 facade、cognitive routes、CLI、registry、bootstrap 的代码现状。
3. 检查了 `state/jobdb.sqlite3` 最近 30 天 live 使用，确认哪些旧面仍有流量、哪些 provider 已真正退休。
4. 对照 planning/Hermes 当前主链，确认哪些 ChatgptREST 能力已被真实采用，哪些仍停留在“做过但未采用”。
5. 将上述结果固化为治理方案文档：
   - `docs/ops/2026-04-17_ChatgptREST新定位治理与退休收口方案_v1.md`

## 为什么这样写

这次不是再写一份泛化评审，而是要给后续维护者一个可执行的治理框架：

1. 哪些能力属于新定位核心资产，应该继续投入。
2. 哪些旧入口还不能删，只能 freeze compat。
3. 哪些能力已经具备立即退休条件。
4. 哪些接口虽然存在，但当前不能继续被叙述成“主路已落地”。

所以正文采用了“四分表 + 分阶段执行 + 验收标准”的结构，而不是纯现状描述。

## 本轮产出

1. 治理方案文档：
   - `docs/ops/2026-04-17_ChatgptREST新定位治理与退休收口方案_v1.md`
2. README 索引补链，便于后续维护者从文档入口直接发现这份方案。

## 当前结论

1. 新定位没有 repo 级完全实现。
2. canonical 主路已经成立。
3. 真正需要治理的不是“是否继续争论定位”，而是：
   - 统一口径
   - 冻结兼容
   - 安排迁移
   - 让已退休/未采用的能力退出错误叙事
