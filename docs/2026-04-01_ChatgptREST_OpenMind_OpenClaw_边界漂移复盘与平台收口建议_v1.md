# 2026-04-01 ChatgptREST / OpenMind / OpenClaw 边界漂移复盘与平台收口建议 v1

## 一句话结论

当前真正的问题，不是“ChatgptREST 独立了”本身，而是：

- **系统事实已经变成共享 AI 控制平面**
- 但**命名、仓库边界、产品叙事、客户端心智模型**仍然停留在“ChatGPT Web REST 后端 / OpenClaw 插件底座”的旧阶段

结果就是：

- 代码层在往平台化演进
- 文档层在混用旧定位和新定位
- 客户端层已经把 ChatgptREST 当作共享后端
- 团队心智仍然在问“它到底是不是 OpenClaw 的插件”

这就是当前“越开发越乱”的根因。

## 结论先行

我的判断是：

1. **是的，存在真实架构问题。**
2. 问题不是功能做多了，而是**边界没有被重新命名和冻结**。
3. 当前最合理的短中期策略，不是马上拆仓，而是先**承认事实并重写边界**：
   - `ChatgptREST` = 共享 AI 控制平面 / runtime 平台
   - `OpenMind` = 该平台内部的 cognitive / advisor substrate
   - `OpenClaw` = 该平台之上的一个 execution shell / client
4. 如果继续不收口，后面每新增一层都会进一步放大：
   - 入口混乱
   - 责任归属模糊
   - northbound surface 漂移
   - 文档失真
   - worktree / 分支 / rollout 现场失控

## 原始定位与当前事实

### 原始设计意图

从现有历史文档看，原始概念更接近：

- `OpenClaw = execution shell`
- `OpenMind v3 = cognitive substrate`
- `ChatgptREST = 底层 ask / jobs / MCP / orchestration 的服务实现载体`

直接证据：

- `ChatgptREST/docs/dev_log/2026-03-10_codex_workstream_end_to_end_summary.md`
  - 明确写了：
    - `OpenClaw = execution shell`
    - `OpenMind v3 = cognitive substrate`

这说明当时的架构心智，不是把 ChatgptREST 当作最终产品平台，而是把它当作承载实现。

### 当前代码与文档事实

但到 2026-04-01，系统事实已经不是这样了。

#### 1. ChatgptREST 已经不是窄后端

`chatgptrest/api/app.py` 当前真实挂载的并不只是 jobs / MCP，而是：

- jobs
- advisor
- consult
- issues
- metrics
- ops
- evomap
- `cognitive_v2`
- `advisor_v3`
- `agent_v3`
- `task_runtime_v1`
- dashboard

也就是说，**ChatgptREST 已经是一个多平面 runtime 平台**，而不是“某个插件依赖的 REST 服务”。

#### 2. ChatgptREST 文档已经把自己定义成 northbound 公共入口

`ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md` 的真实目标是：

- OpenClaw
- Codex
- Claude Code
- Antigravity

统一面向一个 **public advisor-agent facade**。

这意味着 ChatgptREST 的定位已经从：

- “OpenClaw 的后端”

转成了：

- “多客户端共享的高层接入面”

#### 3. OpenClaw 已经被降成客户端

`openclaw/docs/chatgptREST.md` 当前口径非常明确：

- OpenClaw coding-agent 默认走 `public advisor-agent MCP`
- `openclaw-wrapper` 旧的 low-level lane 已被收口
- OpenClaw 不应再维护平行 low-level ask lane

这说明**在实际治理上，OpenClaw 已经不是主壳层 owner，而是一个 client**。

#### 4. ChatgptREST 自己也承认 OpenMind 独立于旧 REST 队列

`ChatgptREST/AGENTS.md` 已明确写出：

- `OpenMind v3 智能顾问管线，独立于上述 REST 作业队列运行`

这又进一步说明：**OpenMind 不是旧 REST jobs 的别名，而是在同一个仓里长出的另一层 runtime**。

## 真实问题不是“独立”，而是“四顶帽子压在一个仓里”

当前 ChatgptREST 实际同时承担了至少四个角色：

1. **低层 Web ask / jobs / MCP service**
   - ChatGPT Web automation
   - `/v1/jobs`
   - MCP adapter

2. **OpenMind cognitive runtime**
   - advisor
   - cognitive
   - consultation
   - northbound reasoning surfaces

3. **共享 northbound facade**
   - public advisor-agent MCP
   - `/v3/agent/*`
   - 多客户端统一入口

4. **新的 task harness / operator plane**
   - task runtime
   - finalization
   - delivery / memory bridge
   - evaluator / decision / promotion

一个仓同时戴这四顶帽子，不做边界收口，就会天然制造：

- 概念重名
- 模块重叠
- owner 不清
- 对外说法不一致

## 为什么你会感觉“越开发越乱”

这不是错觉，而是下面两层问题叠加了。

### 第一层：架构命名漂移

现在至少有 3 个名字已经失真：

#### `ChatgptREST`

名字听起来像：

- ChatGPT Web 的 REST 服务

但真实职责已经远超这个范围，包含：

- cognitive runtime
- public advisor facade
- task harness runtime
- operator plane

#### `OpenMind`

名字听起来像：

- 一个独立产品
- 或至少一个独立核心系统

但现在真实状态更像：

- ChatgptREST 仓内的一层 cognitive / advisor substrate

#### `OpenClaw`

名字听起来像：

- 总壳层 / 主交互产品

但真实治理上它现在只是多个 northbound client 之一。

### 第二层：现场治理漂移

除了架构概念漂移，现场也确实在漂。

截至本次复盘时，ChatgptREST 现场同时存在：

- 主工作树落后 `origin/master`
- 主工作树 dirty
- 大量历史 worktree
- 大量 `prunable` worktree
- 多条一次性集成 / 验证 / PR 检查现场仍然留存

这会放大所有“边界已经不清”的问题，因为团队成员很容易把：

- 架构问题
- rollout 问题
- worktree hygiene 问题

混成一个总体“失控感”。

## 与 Anthropic Harness Best Practice 的对照

参考：

- Anthropic: `Harness design for long-running application development`

Anthropic 那篇文章的重点不是“做多 agent”，而是：

1. `planner / generator / evaluator` 角色分工清晰
2. 每个 sprint 先谈清 `sprint contract`
3. evaluator 是真正 skeptical、带硬阈值的 gate
4. 长任务通过结构化工件和明确 handoff 持续推进
5. feedback 会反向驱动 generator 下一轮实现

### 我们已经有的

- task runtime foundation
- finalization path
- delivery / memory 分层
- evaluator / decision / promotion 雏形
- bootstrap / obligations / closeout / operator 治理面

### 我们还明显缺的

- 真正跑起来的 planner / generator / evaluator 主链
- 每个 chunk / sprint 的前置 contract 协商
- evaluator 的硬阈值 skeptical gate 化
- delivery / memory 的 authoritative runtime 化
- 反馈驱动的稳定多轮闭环，而不是“先实现、再补门禁”

### 所以当前成熟度判断

如果严格按 Anthropic 口径，当前只能定性为：

- **foundation only**

不是：

- `strong intermediate harness`

更不是：

- `close to best-practice`

这点必须说死，不然后续会继续高估成熟度。

## 现在到底该怎么收口

我认为当前有三个战略选项。

### 方案 A：承认 ChatgptREST 已经是主平台

定义改成：

- `ChatgptREST` = 共享 AI 控制平面 / runtime 平台
- `OpenMind` = 内部 cognitive substrate
- `OpenClaw` = 外部 execution shell / client

#### 好处

- 与现实最一致
- 改动最小
- 不需要立刻拆仓
- 方便继续推进 task harness / public facade / operator plane

#### 代价

- 需要正式重写 README、AGENTS、client registry、OpenClaw 文档
- 需要接受“ChatgptREST 这个名字已经不够准确”

### 方案 B：把 OpenMind 真正抽成独立仓 / 独立 runtime

把：

- cognitive / advisor / task harness

从 ChatgptREST 里抽走，ChatgptREST 收回到：

- web ask / jobs / mcp transport / service facade

#### 好处

- 语义最干净
- 产品边界会更清楚

#### 代价

- 当前成本极高
- 会打乱现有 northbound 面
- 需要大规模改入口、文档、部署、运维、测试
- 在当前状态下实施风险大于收益

### 方案 C：不拆仓，但做“强边界化单仓”

保留单仓，但明确分四层：

1. transport / job plane
2. cognitive / advisor plane
3. public agent facade
4. task harness / operator plane

并且在文档、目录、入口、owner 上强制收口。

#### 好处

- 现实可行
- 比方案 A 更清楚
- 比方案 B 风险低

#### 代价

- 仍然保留单仓复杂度
- 需要很严格的分层纪律

## 我的建议

### 短中期建议：A + C 组合

即：

1. **先承认 ChatgptREST 已经是共享平台**
2. **在单仓内做强边界化**

换句话说：

- 不要现在就急着把 OpenMind 拆出去
- 先把“谁是什么”说清楚
- 再把代码和入口按这个新说法整理

这是当前风险最低、收益最高的路线。

## 必须立即做的 6 件事

### 1. 冻结一句唯一真话

建议正式口径：

> ChatgptREST is now the shared AI control-plane runtime.  
> OpenMind is its internal cognitive/advisor substrate.  
> OpenClaw is one execution-shell client on top of that platform.

中文等价版也要同步存在。

### 2. 重写 README 顶部定位

当前 README 的“REST-first job service + thin MCP adapter”已经明显不足。  
必须改成能覆盖：

- public advisor facade
- cognitive runtime
- task runtime
- operator / governance plane

### 3. 重写 OpenClaw 对 ChatgptREST 的关系说明

明确：

- OpenClaw 不再是总壳层 owner
- 它是平台 client
- 它有自己的 shell/runtime concerns
- 但不再定义 ChatgptREST 的产品边界

### 4. 给 OpenMind 一个清晰位置

必须明确 OpenMind 当前到底是：

- 产品名
- runtime 层
- module family
- 还是内部品牌名

不能继续模糊。

### 5. 把 public northbound surfaces 统一登记

必须显式冻结哪些是“默认入口”：

- public advisor-agent MCP
- `/v3/agent/*`
- operator UI
- task runtime API

以及哪些是：

- internal only
- maintenance only
- deprecated

### 6. 做一次 worktree / branch / rollout 现场清理

不然即便架构说清楚了，现场仍会制造“系统很乱”的印象。

## 不建议现在做的事

### 1. 不建议现在就大拆仓

理由很简单：

- 当前核心 northbound surface 正在收口
- task harness foundation 刚成型
- 再做仓级拆分，会把注意力从边界澄清转成搬运工作

### 2. 不建议继续加大功能面

在边界没冻结前继续加功能，只会进一步放大混乱。

### 3. 不建议继续沿用旧名字假装系统没变

这是当前最危险的做法。  
因为这会让所有文档和新开发持续对不上。

## 本次复盘的明确判断

### 不是问题的

- ChatgptREST 演化成共享平台，这件事本身不是原罪
- OpenClaw 变成 client，也不是原罪
- OpenMind 生长成内部 substrate，也不是原罪

### 真正的问题

- **事实已经变了，但叙事没有更新**
- **代码已经平台化，但命名没有平台化**
- **客户端已经收口到 ChatgptREST，但 owner 心智还停在旧架构**

## 建议的下一步文档动作

建议按下面顺序推进：

1. 写一份正式“平台定位冻结文档”
2. 同步改：
   - `ChatgptREST/README.md`
   - `ChatgptREST/AGENTS.md`
   - `ChatgptREST/docs/client_projects_registry.md`
   - `openclaw/docs/chatgptREST.md`
3. 出一份“northbound surface registry”
4. 出一份“repo/worktree cleanup 与 owner 边界清单”

## 最终结论

如果只用一句话总结：

**现在最需要的不是继续写更多功能，而是先承认 ChatgptREST 已经从“OpenClaw 插件后端”演化成“共享 AI 控制平面”，然后围绕这个事实重写边界、命名和现场治理。**

---

## 附：本次判断所依据的核心证据

- `ChatgptREST/AGENTS.md`
- `ChatgptREST/README.md`
- `ChatgptREST/chatgptrest/api/app.py`
- `ChatgptREST/docs/2026-03-17_unified_advisor_agent_surface_convergence_blueprint_v1.md`
- `ChatgptREST/docs/dev_log/2026-03-10_codex_workstream_end_to_end_summary.md`
- `ChatgptREST/docs/client_projects_registry.md`
- `openclaw/docs/chatgptREST.md`
- `git worktree list` 与主工作树 live 状态

## 备注

本稿是基于本地代码与文档事实的第一方复盘结论。  
外部双模型 review 已提交并在 provider 侧执行中，可作为后续第二证据层用于校验或修正文中判断，但不改变当前已经能够从仓内事实独立得出的主结论。
