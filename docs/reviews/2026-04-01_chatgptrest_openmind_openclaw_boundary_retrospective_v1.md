# 2026-04-01 ChatgptREST / OpenMind / OpenClaw Boundary Retrospective v1

## 调查问题

问题原文可以压缩成一句话：

> ChatgptREST 原本是不是准备作为“以 OpenMind 为主的 OpenClaw 插件能力”存在，但后来又越做越像独立系统了？如果是，这是不是架构问题？

本次调查覆盖三层证据：

1. 代码现状
2. 仓库内正式文档与蓝图
3. Git 历史与关键提交波次

## 结论先行

### 一句话结论

是，**边界确实发生了实质性漂移**，而且不是最近一两次误改造成的，而是 2026-02-24 到 2026-03-25 之间连续几轮“增量叠加式收敛”造成的。

但要把问题说准确：

- **如果看仓库根源**，ChatgptREST 从来不是以 OpenClaw 插件起家的，它最早就是一个 REST 作业队列 + web driver host。
- **如果看 3 月上旬的 OpenMind 集成阶段**，确实一度把 OpenClaw 描述成 shell / control plane，把 OpenMind 描述成 cognition substrate，并通过插件集成。
- **如果看 3 月中下旬的落地结果**，仓库又继续把 `public agent surface`、`controller`、`public MCP`、`coding-agent 默认入口` 都内收进 ChatgptREST，使其事实上变成了一个 integrated host。

所以真正的问题不是“怎么突然独立了”，而是：

> **仓库的真实身份已经从单一作业队列，演化成“执行底座 + OpenMind cognition + public agent ingress + controller/finbot ops”的多平面平台，但顶层命名、边界治理、退役策略没有同步跟上。**

## 我看到的 5 个关键事实

### 1. ChatgptREST 的根不是 OpenClaw 插件

当前仓库入口文档仍然把项目基础定位写成：

- `ChatgptREST 是一个 REST 作业队列 + 后台 worker`
- `chatgptMCP driver 已并入本仓库`

证据：

- `AGENTS.md:33-40`
- `docs/handoff_chatgptrest_history.md:8-15`
- `docs/handoff_chatgptrest_history.md:17-33`

这说明仓库底座从一开始就是“自己跑执行面”，不是“纯 OpenClaw 插件包”。

### 2. 到 2026-03-01，仓库已经正式承载 OpenMind v3

`AGENTS.md` 明确写到：

- 本仓库“同时承载 OpenMind v3 智能顾问管线”
- 而且“独立于上述 REST 作业队列运行”

证据：

- `AGENTS.md:188-219`
- `docs/dev_log/2026-03-01_production_launch_readiness.md:7-52`

这一步已经不是“给 OpenClaw 补一个插件”了，而是把第二个系统直接装进同一个仓库。

### 3. 到 2026-03-08，OpenMind 被明确定位成独立 substrate，OpenClaw 反而被降成 optional front-end

这一点不是我主观推断，文档写得非常明确：

- `OpenMind is positioned as the durable cognitive substrate`
- `OpenClaw is an optional execution front-end, not a survival dependency`
- `OpenMind must remain independently valuable`

证据：

- `docs/integrations/openclaw_cognitive_substrate.md:8-20`

同一天的 ADR-002 也把 shell 定义成“thin transport adapter”，真正边界在 domain service，而不是 shell 本身：

- `External shells (OpenClaw, CLI)` 与 `Internal callers (Antigravity, advisor graph)` 都只是 transport
- `Domain Services` 才是 “the REAL boundary”

证据：

- `docs/contracts/ADR-002-ingress.md:16-44`

这说明“从插件走向独立”并不完全是失控漂移，**中途确实发生过一次有意识的架构反转**。

### 4. 但 2026-03-09 的最佳实践蓝图，又把 OpenClaw 重新抬成 shell/control plane

`OpenClaw + OpenMind Best-Practice Blueprint` 又给出了另一套中心叙事：

- `upstream OpenClaw is the shell/runtime/control plane`
- `OpenMind is the durable cognition substrate`
- `role agents exist to serve main, not to become independent product surfaces`

证据：

- `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md:18-31`
- `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md:103-131`

这一步不是错，但它和后面发生的事情没有彻底对齐。

### 5. 2026-03-15 到 2026-03-25，ChatgptREST 又把 public agent/controller 进一步内收成默认入口

先是 controller 被正式推进成 objective-first 执行骨架：

- `controller run` 从 job/request 语义推进到 `objective/run/step`
- `action`、`team` 路径接进 controller 主回路

证据：

- `docs/dev_log/2026-03-15_openmind_controller_unification_walkthrough_v2.md:5-12`
- `docs/dev_log/2026-03-15_openmind_controller_unification_walkthrough_v2.md:38-89`

再到 2026-03-17，public agent facade 明确要求：

- `/v3/agent/turn`
- planner
- judge
- recovery-aware finalization

证据：

- `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md:70-80`
- `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md:134-174`

最后到 2026-03-25，官方维护入口已经明确宣布：

- ChatgptREST 不是单一服务，而是五个 plane 叠加的仓库
- coding agent 默认入口是 ChatgptREST 自己的 public advisor-agent MCP

证据：

- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md:8-16`
- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md:43-90`
- `AGENTS.md:100-137`

这时，仓库已经不只是 OpenMind substrate 了，而是**直接成为 coding-agent 的默认 northbound host**。

## 时间线复原

| 时间 | 发生了什么 | 对边界的影响 |
|---|---|---|
| 2025-12-26 ~ 2025-12-27 | ChatgptREST 继续强化 `/v1/jobs` 契约，并把 chatgptMCP driver 合并进仓库 | 明确是自持执行底座，不是外壳插件 |
| 2026-02-24 | `feat(advisor): add first-class REST and MCP advisor entrypoints` | 在执行仓库里长出 OpenMind/Advisor 第二系统 |
| 2026-03-01 | OpenMind v3 被正式写入 AGENTS 与 production readiness | 仓库从单系统变双系统 |
| 2026-03-08 | Cognitive substrate + OpenClaw plugins + ADR-002/003 | 明确提出“OpenMind 独立有价值，OpenClaw 是可选 front-end” |
| 2026-03-09 | Best-practice blueprint 又强调 OpenClaw 是 shell/control plane | 出现第一处顶层叙事张力 |
| 2026-03-12 | `openmind-advisor` 仍在兼容 `/v2/advisor/advise` 语义 | 旧 advisor 面仍是第一入口之一 |
| 2026-03-15 | controller objective-first 化 | ChatgptREST 开始承担真正 orchestration 语义 |
| 2026-03-17 | `/v3/agent/*` public facade + quality-first 收敛 | ChatgptREST 形成新的统一 agent 面 |
| 2026-03-23 ~ 2026-03-25 | public MCP 被定为 coding-agent 默认入口；五个 plane 被正式分类 | 多平面现实被官方化，但也宣告 repo 身份已经变化 |

## 边界膨胀的量化侧证

我额外看了 2026-02-24 之后的变更分布，结果很能说明问题。

一级目录改动计数里，最高的是：

- `docs`：1712
- `chatgptrest`：1477
- `tests`：1199
- `ops`：479
- `scripts`：473
- `openclaw_extensions`：66

二级目录里，最密集的区域是：

- `docs/dev_log`：1264
- `chatgptrest/api`：281
- `chatgptrest/advisor`：193
- `chatgptrest/kernel`：160
- `chatgptrest/evomap`：143
- `docs/reviews`：134
- `chatgptrest/dashboard`：93
- `chatgptrest/executors`：88
- `chatgptrest/mcp`：60
- `chatgptrest/cognitive`：50
- `chatgptrest/controller`：16
- `openclaw_extensions/openmind-advisor`：29

这组数字说明两件事：

1. 这段时间真正快速膨胀的不是单一插件面，而是 `api + advisor + kernel + evomap + mcp + controller + ops + docs` 的整个平台面。
2. 文档与评审记录的大量增长，说明系统复杂性已经高到必须靠大量补充性文档来维持可维护性。

## 现在真正乱在哪里

### A. 仓库名字还叫 ChatgptREST，但真实身份已经不是“REST 库”

当前真实形态至少包含：

1. execution substrate
2. OpenMind advisor / KB / memory / graph substrate
3. public agent facade + public MCP
4. controller / finbot / orch / guardian 运行面
5. dashboard / read model

这不是我夸张，维护入口就是这么写的。

证据：

- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md:8-16`
- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md:82-90`

问题是，**命名还是单一，现实却是多平面平台**。这会直接制造错误预期。

### B. 顶层“谁是默认入口”存在按客户端切分的双重叙事，但没有被一页纸讲透

对 OpenClaw 集成文档：

- OpenClaw 是 shell/runtime/control plane

对 coding agent 维护文档：

- ChatgptREST public MCP 是默认 northbound surface

这两句话并不严格互斥，因为用户群不同：

- OpenClaw 用户
- Codex / Claude Code / Antigravity 用户

但问题在于，仓库没有在最顶层明确写出：

> “默认入口按 client class 分裂，OpenClaw 是 shell-facing primary，public MCP 是 coding-agent-facing primary。”

结果就是任何接手的人都会产生和这次一样的困惑。

### C. public agent 并不是薄适配器，而是新的集成中枢

`routes_agent_v3.py` 顶部同时耦合了：

- advisor contract / strategist / prompt builder
- `ControllerEngine`
- job store
- workspace service
- cognitive memory capture

证据：

- `chatgptrest/api/routes_agent_v3.py:1-10`
- `chatgptrest/api/routes_agent_v3.py:33-72`

同时，它还明确拦截 Codex / Claude / Antigravity 等客户端直接打裸 REST：

- 允许的是 `chatgptrest-mcp` 和 `openclaw-advisor`

证据：

- `chatgptrest/api/routes_agent_v3.py:94-107`

并且它内部依然会把 route 映射回原来的 `chatgpt_web.ask` 等低层 substrate：

- `chatgptrest/api/routes_agent_v3.py:3366-3384`

这说明 public agent 不是平行系统，而是**新的统一编排壳**。这进一步强化了“integrated host”现实。

### D. OpenClaw 插件自身也经历了入口收敛，说明边界一直在移动

2026-03-08 的 integration 文档还写：

- `openmind-advisor` backend 是 `/v2/advisor/ask` 和 `/v2/advisor/advise`

证据：

- `docs/integrations/openclaw_cognitive_substrate.md:83-99`

但当前插件 README 已经写成：

- 插件直接调用 `POST /v3/agent/turn`

证据：

- `openclaw_extensions/openmind-advisor/README.md:17-25`

这不是小改动，而是**从旧 advisor 面转向 public agent contract 的实质收敛**。

### E. 演化方式几乎一直是 additive，不是 replace

`Unified Advisor Agent Surface Convergence Blueprint v2` 明说：

- 一次性完成 public `/v3/agent/*`
- OpenClaw advisor plugin convergence
- CLI / wrapper convergence
- 同时保持 `additive`、`backward compatible`、`不删除旧入口`

证据：

- `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md:165-180`

这很务实，但副作用也很清楚：

- 新入口不断长出来
- 旧入口不退役
- 操作守则越来越长
- 维护者只能靠“矩阵 + guardrail + 禁令”避免误用

这正是“越开发越乱”的技术成因。

## 不是所有变化都该被判错

必须说一句公道话：

### 有意识、而且合理的部分

1. 把 OpenMind 变成独立 substrate，本身并不荒唐。
2. 让 OpenClaw 成为可选 shell，也有现实价值。
3. 给 coding agent 一个不必依赖 OpenClaw 的 public MCP，也符合实际使用需求。
4. 用 controller/public agent 复用旧 execution substrate，而不是重写一遍，也很务实。

### 真正的问题

真正的问题不是“独立了”，而是：

1. **没有一次 repo-level 重新命名/重新定位**
2. **没有一次清晰的 authority matrix 冻结**
3. **没有旧入口的退役时间表**
4. **没有把“不同 client class 对应不同 primary surface”写成单一 top-level mouthpiece**

也就是说，问题更像**治理失配**，不是单点设计失误。

## 我的判断

### 结论 1

如果你现在仍把它理解成：

> “ChatgptREST 是 OpenMind 的 OpenClaw 插件承载库”

那这个理解已经**不符合当前事实**了。

### 结论 2

如果你现在把它理解成：

> “ChatgptREST 是一个 integrated runtime host；里面承载 execution substrate、OpenMind cognition、public coding-agent ingress；OpenClaw 是外部 shell/automation client 之一”

这个理解和现状更接近。

### 结论 3

所以，**是有问题**，但问题不是“独立化”本身，而是“架构反转已经发生，却没有被顶层治理彻底承认并清场”。  

这会持续带来：

1. 入口误用
2. 责任归属模糊
3. 文档暴涨
4. 新功能落位随手就能跨 plane
5. 维护者心理模型不断失真

## 建议怎么收拾

### 方案选择上，我建议先承认现实，不要继续嘴上说插件、手上做平台

最务实的短期方向不是“强行退回 OpenClaw-primary”，而是先写清现实：

> **ChatgptREST 是 integrated host；OpenMind 是其 cognition substrate；OpenClaw 是 optional shell/client；public MCP 是 coding-agent 默认入口；`/v1/jobs` 是 maintenance-grade substrate。**

如果不先承认现实，后面所有整顿都会继续在错名下进行。

### 需要立刻补的 6 件事

1. 新增一个 repo-level ADR
   - 不是 cognitive ADR
   - 不是 ingress ADR
   - 而是 “Repo Identity / Authority Matrix / Surface Hierarchy”

2. 冻结一张 authority table
   - 谁拥有 session
   - 谁拥有 delivery
   - 谁拥有 memory / KB / telemetry
   - 谁拥有 user-facing primary ingress
   - 谁只是 adapter

3. 冻结一张 surface hierarchy
   - coding agent primary
   - OpenClaw primary
   - internal substrate
   - maintenance-only legacy

4. 给旧入口写退役矩阵
   - `/v1/jobs kind=*web.ask`
   - `/v2/advisor/ask`
   - `/v2/advisor/advise`
   - 旧 role-agent / orch lane
   - broad/admin MCP

5. 把文档 mouthpiece 收敛成 1 份
   - AGENTS + maintainer entry + one architecture ADR
   - 不要再让 devlog 变成事实来源的主口

6. 给 repo 做逻辑分区，必要时再决定是否物理拆仓
   - `execution`
   - `openmind-substrate`
   - `public-agent`
   - `openclaw-extensions`
   - `controller-finbot`

## 最后的直接判断

你现在觉得“越开发越乱”，这个感觉是对的。

但更准确的说法不是：

> “本来做插件，后来做歪了。”

而是：

> “这个仓库已经连续几次升级自己的角色，从作业队列变成 cognition host，再变成 public agent/controller host；技术实现很多是合理的，但顶层身份和退役治理没有同步完成，所以系统开始同时说几种话。” 

这才是这次复盘里最核心的结论。

## 本次主要证据清单

- `AGENTS.md:33-40`
- `AGENTS.md:100-137`
- `AGENTS.md:188-219`
- `docs/handoff_chatgptrest_history.md:8-15`
- `docs/dev_log/2026-03-01_production_launch_readiness.md:7-52`
- `docs/contracts/ADR-002-ingress.md:16-44`
- `docs/integrations/openclaw_cognitive_substrate.md:8-20`
- `docs/integrations/openclaw_cognitive_substrate.md:67-99`
- `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md:18-31`
- `docs/integrations/openclaw_openmind_best_practice_blueprint_20260309.md:103-131`
- `docs/dev_log/2026-03-12_advisor_path_convergence_walkthrough_v2.md:17-35`
- `docs/dev_log/2026-03-15_openmind_controller_unification_walkthrough_v2.md:15-89`
- `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md:70-80`
- `docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v2.md:134-180`
- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md:8-16`
- `docs/ops/2026-03-25_agent_maintainer_entry_v1.md:43-90`
- `chatgptrest/api/routes_agent_v3.py:1-10`
- `chatgptrest/api/routes_agent_v3.py:33-72`
- `chatgptrest/api/routes_agent_v3.py:94-107`
- `chatgptrest/api/routes_agent_v3.py:3366-3384`
- `openclaw_extensions/openmind-advisor/README.md:17-25`
