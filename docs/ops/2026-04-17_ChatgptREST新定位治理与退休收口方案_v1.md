---
title: ChatgptREST新定位治理与退休收口方案
status: current governance plan
updated: 2026-04-17
owner: Codex
---

# ChatgptREST新定位治理与退休收口方案

## 一 目的

本文用于把本轮 fresh 审计固化成一份可执行治理方案，回答四个问题：

1. ChatgptREST 新定位到底哪些部分已经实现。
2. 哪些功能应继续保留并投入。
3. 哪些功能应冻结兼容而不是继续扩展。
4. 哪些功能应立即退休，哪些虽然开发过但当前并未进入主链。

本文是 `docs/ops/*` 平面的 current governance plan，不是历史回顾文档。

## 二 冻结目标状态

当前冻结定位不是“删光旧系统”，而是把 ChatgptREST 收口为明确的后端角色。

### 2.1 角色归位

| 系统 | 冻结角色 | 目标状态 |
| --- | --- | --- |
| Hermes / planning workbench | 前台工作面 | 唯一默认主前台 |
| ChatgptREST | 后端认知、记忆、自动化能力池 | 被 Hermes 和 coding agents 作为 shared backend 使用 |
| OpenClaw / 旧 facade | 兼容层与历史参考 | freeze compat，不再作为默认主线 |

### 2.2 ChatgptREST 目标保留面

1. `automation-kernel-v1` / public MCP `automation_*`
2. 低层 job / worker / browser automation substrate
3. `/v2/context/resolve`
4. `/v2/graph/query`
5. `/v2/memory/capture`
6. 内部观测与维护所需的 narrow runtime plane

### 2.3 不再允许的默认叙事

以下叙事应退出 current canonical guidance：

1. `advisor-agent MCP` 是 coding agent 默认 northbound surface。
2. `coding_agent_*` 是 public shared MCP canonical toolset。
3. `qwen_web.ask` 是当前 live provider。
4. `/v3/agent/*` 是对 coding agents 的默认共享入口。

## 三 当前 fresh 盘点结论

## 3.1 已经成立的部分

### A. canonical 主路已建立

当前 public MCP 的 canonical 共享后端已经切到 `automation-kernel-v1` / `automation_*`，并且 planning/Hermes 已真实消费：

1. `automation_ask`
2. `/v2/context/resolve`
3. `/v2/graph/query`
4. `/v2/memory/capture`

这意味着“新定位的主路”不是空谈，已经在真实前台主链里成立。

### B. `qwen_web.ask` 已在代码和 runtime 层退休

运行时与 provider registry 已把 Qwen ask 标成 removed，最近 30 天 live job 也为 `0`。

这类功能已经满足“可进入退休状态”的条件。

## 3.2 尚未完全实现的部分

### A. 旧前台 / 旧 facade 仍在 live 流量里活着

fresh runtime 审计显示，最近 30 天仍有：

- `advisor_ask = 389`
- `agent_v3 = 196`
- `advisor_agent_turn = 20`

这说明旧面不是纯死代码，而是仍在被使用的 compat surface。

### B. 机器口径与人类口径仍然漂移

虽然 `AGENTS.md` 和 `docs/contract_v1.md` 已切到 `automation_*` 口径，但下列面仍在教旧默认：

1. `chatgptrest/cli.py`
2. `ops/registries/surface_policy.yaml`
3. `ops/registries/runtime_registry.yaml`
4. `README.md`
5. `CLAUDE.md`
6. `GEMINI.md`
7. 仍以 `coding_agent_*` 为主验收面的部分 harness / tests

### C. 一批认知接口“做了，但没进入新主链”

当前没有证据表明这些接口已经成为 Hermes / coding agent 日常主路：

1. `/v2/knowledge/ingest`
2. `/v2/kb/upsert`
3. `/v2/policy/hints`

它们应从“已完成主路能力”叙事里剥离，转为“待证明价值的保留能力”。

## 四 治理决策四分表

## 4.1 保留并继续投入

这些能力属于新定位的核心资产，不应退休：

| 类别 | 项目 | 决策 | 说明 |
| --- | --- | --- | --- |
| shared backend | public MCP `automation_*` | 保留并继续投入 | 当前 canonical 主路 |
| execution substrate | `/v1/jobs`、worker、driver、job artifacts | 保留并继续投入 | automation backend 的运行底座 |
| providers | `chatgpt_web.ask`、`gemini_web.ask` | 保留并继续投入 | 当前 live 主执行器 |
| cognition | `/v2/context/resolve` | 保留并继续投入 | planning/Hermes 已使用 |
| cognition | `/v2/graph/query` | 保留并继续投入 | planning/Hermes 已使用 |
| memory | `/v2/memory/capture` | 保留并继续投入 | planning/Hermes 已使用 |
| internal ops | `/v2/telemetry/ingest` | 保留但重新归类 | 保留为内部观测桥，不再对外包装成 Hermes 核心主能力 |

## 4.2 冻结兼容

这些能力当前不能直接删除，因为仍有 live 依赖；但它们必须进入 freeze compat：

| 项目 | 当前状态 | 治理决策 |
| --- | --- | --- |
| `advisor_ask` | 仍有 live 流量 | freeze compat；禁止新功能；迁移后再退 |
| `advisor_agent_*` | 仍有 live 流量 | freeze compat；仅保留兼容与迁移 |
| `coding_agent_*` | 仍在旧 harness / compat 中出现 | freeze compat；退出 canonical 叙事 |
| `/v2/advisor/*` | 旧前台能力面 | freeze compat |
| `/v3/agent/*` | 旧前台能力面 | freeze compat；不得再作为默认 shared backend 教学面 |
| `consult` / 旧 facade router | 仍挂载于 app | freeze compat；待流量清零后评估卸载 |
| 仍以 `coding_agent_*` 为主的 live gate / eval harness | 仍承担一部分验收 | 改标为 compat gate，或迁移到 `automation_*` |

冻结兼容的硬规则：

1. 不再给 compat surface 增加新产品能力。
2. 只允许做 bugfix、contract hardening、migration aids。
3. 所有 compat surface 文档必须显式标注 `legacy / compat / non-canonical`。

## 4.3 立即退休

这些项已经满足“应立即退出 current guidance”的条件：

| 项目 | 当前事实 | 决策 |
| --- | --- | --- |
| `qwen_web.ask` runtime 能力 | 代码已 retired，最近 30 天 live 使用为 0 | 立即从 runbook / contract / examples / smoke 教程中退休 |
| “advisor-agent MCP 是默认入口”口径 | 与当前 canonical 冲突 | 立即退休 |
| “coding-agent-v1 是默认 northbound surface”口径 | 与当前 canonical 冲突 | 立即退休 |
| README / CLAUDE / GEMINI 中旧默认 surface 教学 | 误导新调用方 | 立即退休 |
| registry / bootstrap 中 `coding_agent_*` canonical 提示 | 会污染机器 guidance | 立即退休 |

## 4.4 已开发但未采用

这些能力不应再被写成“新定位已完成项”：

| 项目 | 当前判断 | 决策 |
| --- | --- | --- |
| `/v2/knowledge/ingest` | 已实现，未进入 Hermes 日常主链 | 保留代码，暂停叙事；等待真实 consumer |
| `/v2/kb/upsert` | 已实现，未进入 Hermes 日常主链 | 保留代码，暂停叙事；等待真实 consumer |
| `/v2/policy/hints` | 已实现，未进入 Hermes 日常主链 | 保留代码，暂停叙事；等待真实 consumer |
| “认知资产抽取 / 重宿主化” | 目前仅是路线，不是已执行工程 | 保留为后续阶段，不纳入本轮已完成叙事 |

## 五 执行计划

## G0 口径与入口统一

目标：让 repo 的 current guidance、机器 guidance、CLI guidance 先说同一种话。

### G0.1 需要更新的 mouthpiece

1. `chatgptrest/cli.py`
2. `ops/registries/surface_policy.yaml`
3. `ops/registries/runtime_registry.yaml`
4. `ops/registries/plane_registry.yaml`
5. `README.md`
6. `CLAUDE.md`
7. `GEMINI.md`
8. `docs/runbook.md`
9. `docs/contract_v1.md`
10. `scripts/chatgptrest_bootstrap.py` 相关 surface 投影依赖

### G0.2 目标状态

1. canonical public surface 统一写成 `automation-kernel-v1` / `automation_*`
2. `coding_agent_*` / `advisor_agent_*` 统一降格为 compat / maintenance / legacy
3. Qwen 从 current docs 和 smoke 示例中移除

### G0 完成标准

1. bootstrap packet 中 `surface_policy.public_mcp_ingress_contract.primary_tools` 变成 `automation_*`
2. CLI 默认 surface 不再是 `coding-agent-v1`
3. README / CLAUDE / GEMINI 不再教授旧默认入口

## G1 兼容面冻结治理

目标：把“还在活”的旧面正式转成 compat，不再伪装成主路。

### G1.1 动作

1. 对 `advisor_ask`、`advisor_agent_*`、`coding_agent_*`、`/v2/advisor/*`、`/v3/agent/*` 加一致的 compat 标识
2. 对相应 docs / health / tool descriptions 加 `non-canonical` 语义
3. 在 live gate / eval harness 中区分：
   - canonical gate
   - compat gate

### G1.2 完成标准

1. 任一新维护者不会再把 compat 面误当 default shared backend
2. compat 面仍可服务现有调用方，但新增功能默认不再落在 compat 面

## G2 流量迁移与清零

目标：把仍在使用 compat 面的调用方迁到 canonical 主路。

### G2.1 迁移对象

1. `advisor_ask`
2. `agent_v3`
3. `advisor_agent_turn`
4. 仍使用 `coding_agent_*` 的 eval / harness / wrappers

### G2.2 动作

1. 基于 `docs/client_projects_registry.md` 对客户端逐一建迁移清单
2. 为每个客户端指定：
   - 当前入口
   - 目标入口
   - 迁移 owner
   - 迁移截止条件
3. 对 compat 调用方增加迁移证据：
   - last consumer
   - last success
   - current fallback reason

### G2.3 完成标准

1. compat 流量在 30 天窗口内持续归零，或仅剩明确批准的 maintenance use
2. planning/Hermes、Codex/Claude Code/Antigravity 的默认 wrapper 全部走 `automation_*`

## G3 退休收口

目标：让已经退休或满足退休条件的东西退出 runtime narrative 与 current docs。

### G3.1 第一批立即退休

1. Qwen docs / examples / smoke instructions
2. 旧默认入口口径
3. registry / bootstrap 里的旧 canonical surface 提示

### G3.2 第二批条件退休

以下项只有在 live 兼容流量清零后才能动 runtime：

1. `advisor_agent_*`
2. `coding_agent_*`
3. `/v2/advisor/*`
4. `/v3/agent/*`
5. `consult` router

### G3.3 完成标准

1. 退休项在 current docs 不再出现为 live capability
2. 条件退休项在满足流量清零条件前，保持 compat 冻结；满足后再卸载

## G4 “已开发但未采用”能力的去神话化

目标：停止把 dormant APIs 包装成已完成主路能力。

### G4.1 动作

1. 对 `knowledge_ingest`、`kb_upsert`、`policy_hints` 明确标注：
   - experimental / internal
   - not on current Hermes mainline
2. 为每项能力定义二选一命运：
   - 找到真实 consumer 并进入主路
   - 在后续版本中转入 internal-only / archive 候选

### G4.2 完成标准

1. 仓库不再把这些能力写成“新定位已落地”的一部分
2. 每个能力都有明确 owner 和下一步去向

## 六 验收标准

本治理方案收口完成，至少要满足以下条件：

1. `automation_*` 成为 repo 内外一致的 canonical 共享后端口径
2. CLI、registry、bootstrap、README、runbook 不再教旧默认
3. `qwen_web.ask` 从 current docs 和操作手册中完全退休
4. compat surfaces 全部被明确标注为 `legacy / compat / non-canonical`
5. 最近 30 天 compat 流量降到可解释、可批准的窄范围
6. `knowledge_ingest`、`kb_upsert`、`policy_hints` 被重新归类，不再被误写成已完成主路能力

## 七 非目标

这份治理方案不包含以下工作：

1. 立即删除所有旧入口代码
2. 当场进行“认知资产抽取重宿主化”
3. 对所有历史 artifact / dev log 做全面重写

当前目标是先把口径、治理分类、迁移顺序和退休条件收口正确。

## 八 一句话结论

ChatgptREST 的新定位已经在 canonical 主路上成立，但 repo 仍处于“新主路已建立、旧入口仍活、文档与工具链仍在教旧世界、部分能力做了却没被采用”的过渡态。  
本方案的目标不是再争论定位，而是把保留、冻结兼容、立即退休、暂停叙事四类对象一次性收口清楚。
