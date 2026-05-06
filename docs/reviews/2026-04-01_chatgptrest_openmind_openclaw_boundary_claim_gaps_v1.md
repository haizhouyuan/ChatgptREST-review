# 2026-04-01 ChatgptREST / OpenMind / OpenClaw Boundary Claim Gaps v1

## Conflicted

- `C13`
  - 命题：当前系统存在一个统一、无冲突的默认产品叙事。
  - 冲突来源：
    - `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md` 把 OpenClaw 定为 shell/runtime/control plane。
    - `AGENTS.md` 与 `docs/ops/2026-03-25_agent_maintainer_entry_v1.md` 又把 ChatgptREST public MCP 定为 coding-agent 默认 northbound surface。
  - 当前判断：
    - 这两者不是绝对逻辑冲突，因为面向的 client class 不同。
    - 但仓库顶层没有一页纸把这种“按客户端分裂的 primary surface”讲清楚，因此对维护者构成真实混乱。

## Gap

- `G01`
  - 缺口：缺少 repo-level identity ADR。
  - 现状：
    - 有 `ADR-002-ingress`、`ADR-003-identity` 这类局部 ADR。
    - 没有一个顶层 ADR 明确：
      - ChatgptREST 是什么
      - OpenMind 是什么
      - OpenClaw 在这个仓库里到底是什么角色
      - public agent / controller / finbot 是否属于主产品面

- `G02`
  - 缺口：缺少正式退役矩阵。
  - 现状：
    - 文档大量使用 `primary` / `legacy fallback` / `maintenance-only` / `retired` 等标签。
    - 但看不到一个公开、稳定的“什么时候退、退哪些、谁不能再接入”的时间表。

## 我对这些 conflict / gap 的解释

- 当前混乱主要不是因为“代码功能做错了”。
- 当前混乱主要是因为：
  - 顶层身份没有冻结
  - 旧入口没有退役时间表
  - 不同客户端的 primary surface 被动分裂后，没有统一 mouthpiece
