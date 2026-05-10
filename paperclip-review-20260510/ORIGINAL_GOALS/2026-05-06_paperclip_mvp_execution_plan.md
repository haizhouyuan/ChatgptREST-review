# Paperclip MVP 实施计划

> 日期: 2026-05-06  
> 状态: v0 controller plan  
> 目标: 先打通一个能用的 Paperclip 公司化 MVP，再决定哪些底层工程值得继续硬化。  
> 约束: 不继续扩大 runtime_allocator；不把历史文档当路线锁定；不让 agent 自动写长期 authority；不把已无 credits 的 runtime 放进有效池。

---

## 1. 我的路线判断

### 1.1 PCL Runtime / PECL Runtime Steward Company 的价值

它有价值，但不是现在的产品主线。

当前 live 状态：

- company: `PECL Runtime Steward Company 20260503`
- agents: `PECL Memory Steward`, `PECL Skill MCP Governance Steward`
- projects: 1
- issues: 18，其中大部分是 runtime bridge / canary / steward smoke。

判断：

- 这家公司更像 Codex 帮你开发 Paperclip 过程中留下的 **runtime/governance 实验室**。
- 它证明过一些接口、canary、issue/gate、memory/skill steward 的想法，但没有真正变成你日常可用的公司。
- 它现在不应该承担“治理公司”的真实职责，否则会和你想要的治理公司、Memory Research Lab、Skill/MCP agent 混在一起。

策略：

- **保留，不删除**：作为 runtime / gate / steward canary 的历史实验资产。
- **降级，不主推**：不再把它当主力业务公司，不让它继续吞主线 token。
- **提取可复用部分**：issue/gate/canary 经验、Paperclip API 操作经验、runtime bridge 经验。
- **职责迁移**：
  - 真正的治理公司负责跨公司治理、skill/MCP、记忆管理。
  - Learning Research Company 负责研究 memory/runtime/skill 的方案。
  - PCL Runtime company 只保留为 infra lab / compatibility lab。

建议后续在 Paperclip 里把它标记为：

```text
status: active 或 archived 待定
role: infrastructure lab / historical runtime steward
not_for_daily_task_intake: true
```

### 1.2 为什么不能继续先硬化 runtime_allocator

runtime_allocator 现在的问题是：它会让团队很容易进入“先把底层做完”的陷阱。你的真实目标是：

- Planning Work Assistant 能接需求、做规划、会议、人资、文档。
- Finbot 能把投研信息变成可跟踪、可复盘、可行动的研究资产。
- 治理公司能帮其他公司维护 memory/skill/MCP。
- Hermes 以后能做 intake，Paperclip 自动拆任务。

这些目标第一版不需要完整 allocator。第一版只需要：

1. 手工维护一个 runtime matrix。
2. 每次任务跑前做轻量 preflight。
3. 失败时人工选择 fallback。
4. closeout 时记录哪个 runtime 有效。

所以：runtime_allocator 进入 backlog。只有当 MVP 跑通、任务量上来、手工路由明显成为瓶颈时，才继续 P0/P1/P9。

---

## 2. 修正后的有效 runtime 池

### 2.1 当前可纳入 MVP 的 runtime

| Runtime | 用途 | 策略 |
|---|---|---|
| codex1 / codex | 总控、最终把关、复杂实现 | 保留为 controller，不把重复 token 工作都压给它 |
| claudekimi | 长链执行、证据合成、复杂研究任务 | 主力 worker，但任务必须有短 contract |
| claudeminmax | 批量整理、重复 review、低风险自动化、多模态资源 | 大量榨干；适合跑对比测试、表格整理、Finbot 批处理 |
| claudeds | DeepSeek 编程/低价缓存实验 | 作为 coding fallback 和成本评估 lane |
| Kimi Code / kimicode | native CLI / ACP candidate | 需要补做 Paperclip native ACP 接入核验 |
| gemini CLI | 外部第二视角、多模态/Google 生态 | 用于补充评审或资料处理 |
| HomePC Ollama | 本地模型研究候选 | research-only；在本地模型质量、稳定性、fallback 研究完成前，不参与系统搭建或真实任务路由 |

### 2.2 当前移出有效池

| Runtime | 处理 |
|---|---|
| claudegac | credits 已用完，不再作为 Finbot 或战略红队默认 runtime |
| claudemi | credits 已用完，不再作为 fallback |

---

## 3. 组织策略

### 3.1 最小公司图

第一轮只保留 4 个实用公司，不再扩张：

1. **Governance Company**
   - 治理其他公司。
   - 记忆管理 agent。
   - Skill/MCP agent。
   - 不做具体业务产出。

2. **Planning Work Assistant**
   - 主力高频公司。
   - 只先打通 3 条用户最常用工作流：
     - strategy brief
     - HR / organization note
     - meeting recording -> action / decision extract

3. **Finbot Investment Research**
   - 个人投研。
   - 当前阶段只做现状调查、问题分析、历史资产盘点、框架选型。
   - 暂不搭建新系统，暂不启动自动化研究流，暂不做 watchlist / decision queue 的生产落地。

4. **Learning Research Company**
   - 做 memory/runtime/skill 方法研究。
   - 输出方案、eval、Pro packet、candidate improvements。
   - 不直接代替 Governance Company 执行治理。

其他公司：

- Labebe AI Transformation 保留 demo/MVP。
- Local LLM Research 可以先作为 Learning Research Company 的 project，不急着独立增强。
- PCL Runtime company 降级为 infra lab。

### 3.2 职责边界

| 能力 | 放在哪里 | 不放在哪里 |
|---|---|---|
| 记忆系统研究 | Learning Research Company | Planning Work Assistant 日常执行流 |
| 记忆管理落地/写入策略 | Governance Company | PCL Runtime company |
| Skill/MCP lifecycle | Governance Company | 每个业务公司自己散管 |
| runtime preflight / matrix | Governance Company + Learning Research | runtime_allocator 全自动 |
| Planning 日常任务 | Planning Work Assistant | Research company |
| 投研系统调研与框架选型 | Finbot research lane | ChatgptREST artifacts 散落目录 |

---

## 4. Planning Work Assistant MVP

### 4.1 目标

让它成为你最常用的工作助手，不先追求完整自治。

MVP 只打通：

1. **Strategy Brief**
   - 输入：碎片想法 / 当前项目 / 一个问题。
   - 输出：1 页结构化判断、可选方案、下一步 issue。

2. **HR / Organization Note**
   - 输入：组织、岗位、agent/company 调整想法。
   - 输出：职责边界、冲突点、建议组织图、待确认问题。

3. **Meeting Recording Intake**
   - 输入：会议录音/转写。
   - 输出：decision、action、open gaps、owner、follow-up。

### 4.2 首轮不做

- 不先接完整 Graphiti / MemPalace / Supermemory 生产写入。
- 不让它自动修改其他公司。
- 不做大而全 dashboard。
- 不把历史 planning 文档当默认真相。

### 4.3 记忆接入方式

第一轮用“读前 brief + 收尾 delta proposal”，不做自动长期写入：

```text
Preflight:
- 当前任务 contract
- 相关历史材料索引
- 当前 authority 摘要
- 禁止事项

Closeout:
- 产物路径
- 决策/任务/gap
- candidate memory_delta
- 是否需要人工批准写入
```

---

## 5. Finbot 调研与框架选型策略

### 5.1 历史资产判断

已找到三类资产：

1. `codexread`
   - 有成熟的投研规格：
     - `decision-package-spec.md`
     - `investing-monitoring-spec.md`
     - `signals-alerts-spec.md`
   - 有 topic investing、watchlist、universe、signals、alerts、decision package 脚本。
   - 价值：**投研资产模型和证据/决策 gate**。

2. `finchat`
   - 投研驾驶舱，连接 `finagent`。
   - 当前 UI 定位是 Today / Theses / Targets / Sources / Queues / Journal / Chat。
   - 价值：**可视化驾驶舱和日常 review 界面**。

3. `ChatgptREST/artifacts/finbot` + `finbot_modules`
   - 已有 theme radar、research package、opportunities、source scoring、posture guard、promotion packet。
   - 价值：**已有研究成果和自动化规则**。

4. `toyresearch/paperclip_finbot`
   - 有 Paperclip Finbot Orchestrator + TradingAgents adapter。
   - 但现在过重，且硬 pin claudekimi。
   - 价值：**可作为一个实验 adapter，不作为第一版核心**。

### 5.2 当前阶段目标

不要一上来追求“自动给买卖建议”，也不要马上重启系统搭建。当前阶段目标是：

```text
1. 查清楚之前到底做过哪些投研工作；
2. 判断为什么没有形成有效投资决策；
3. 梳理哪些资产能复用，哪些要废弃；
4. 结合附件方法论，比较未来框架选型；
5. 输出一个不实施、只供决策的 Finbot framework recommendation。
```

### 5.3 首轮产物形态

Finbot 当前不是 MVP 实现，而是 `Current-State Audit + Problem Diagnosis + Framework Selection`。

最小研究流：

```text
ChatgptREST/codexread/finchat historical assets
  -> source registry
  -> capability inventory
  -> failure analysis
  -> reusable asset map
  -> framework options
  -> recommendation
```

### 5.4 首批主题

直接复用已有资产，不重新发明：

- 变压器超级周期。
- 硅光 / CPO。
- AI 能源 / 现场发电。
- 存储分化。
- 商业航天。

这些主题只作为历史样本，不进入真实跟踪。每个主题只用于回答：

- 当时的研究输入是什么。
- 产物停在了哪一层。
- 缺什么证据或决策 gate。
- 是否适合作为未来框架的测试样本。

### 5.5 首轮不做

- 不做自动交易。
- 不做实时行情高频系统。
- 不把 TradingAgents 多 agent 全量搬进 Paperclip。
- 不让 13 个 Finbot agents 同时跑。
- 不用 claudegac。
- 不创建生产 watchlist / decision queue。
- 未读取用户提供的两份附件前，不冻结 Finbot 框架选型。

---

## 6. Learning Research Company MVP

### 6.1 目标

它不是生产公司，是“帮其他公司变聪明”的研究公司。

首轮只做三件事：

1. Memory research:
   - 把 Graphiti / MemPalace / Supermemory / GBrain / thought-retriever 的架构研究补完。
   - 输出 Planning 可用的最小 preflight / closeout memory protocol。

2. Skill/MCP research:
   - 审计现有 skills/MCP。
   - 调研 Superpowers / gstack / SkillPort。
   - 输出“保留、淘汰、引入候选”清单。

3. Runtime research:
   - 修正 runtime pool。
   - 补 Kimi Code ACP。
   - 做 claudeminmax / claudeds 的低成本任务适配测试。
   - HomePC Ollama 只做本地模型研究，不进入系统搭建任务。

### 6.2 首轮工作方式

研究公司只产出：

- research packet。
- comparison table。
- recommendation。
- MVP spec。
- Pro question packet。

不直接改生产配置。

---

## 7. 总控方法论

### 7.1 我作为 controller 的工作方式

每一轮只做一个可见闭环：

1. 定义任务 contract。
2. 指派一个公司/agent 或本地脚本执行。
3. 限制 token 和时间。
4. 收取产物。
5. 做验收。
6. 决定保留/返工/停止。
7. 写回 Paperclip issue 和 current truth。

### 7.2 Token 控制规则

- Codex 只做总控、验收、关键实现。
- claudekimi 做较复杂的研究/整理，但必须给短 prompt 和明确产物。
- claudeminmax 做批量、重复、低风险工作。
- HomePC Ollama 暂不参与后台 digest/抽取；只在本地模型研究通过后作为未来自动化降本候选。
- Pro 只用于“冻结方向/关键架构评审”，不用于日常大扫仓。

### 7.3 每个任务的最小 contract

```text
goal:
input_paths:
allowed_write_paths:
forbidden:
runtime:
max_time:
max_tokens_or_scope:
expected_output:
acceptance:
stop_condition:
```

没有 contract，不启动 agent。

---

## 8. 48 小时实施计划

### Step 1: 冻结当前状态，不继续扩复杂度

产物：

- `Paperclip Company Role Map v0`
- `Runtime Effective Pool v0`
- `PCL Runtime Company Downgrade Decision`

验收：

- claudegac / claudemi 不再出现在有效路由里。
- Kimi Code / ACP 被列为待核验 runtime。
- PCL Runtime company 被标注为 infra lab。

### Step 2: Seed Planning MVP

产物：

- Planning Work Assistant 3 个 project：
  - Strategy Brief Intake
  - HR / Organization Note
  - Meeting Recording Intake
- 每个 project 2-3 个 issue。

验收：

- 能从一个自然语言输入生成 task contract。
- 能产出一个 strategy brief。
- 能 closeout candidate memory_delta。

### Step 3: Finbot 现状调查与框架选型

产物：

- Finbot current-state audit。
- Finbot historical asset map。
- Finbot failure analysis。
- Finbot framework option matrix。
- 附件读取任务：`个人投研助理方法.md`、`投研助理插件推荐.md`。

验收：

- 只回答“现状是什么、为什么过去没形成效果、未来应选什么框架”。
- 不启动新系统实现。
- 不创建生产 watchlist / decision queue。
- 未读附件前，框架选型只能标记为 provisional。

### Step 4: Seed Learning Research MVP

产物：

- Memory Research project。
- Skill/MCP Research project。
- Runtime Research project。

验收：

- 每个 project 有清晰的第一轮 research packet。
- Pro 咨询问题不是开放发散，而是带 facts + questions。

---

## 9. 7 天目标

- Planning Work Assistant 能真实处理 3 类输入。
- Finbot 完成现状调查、问题分析和框架选型建议；不要求每周 review 页面上线。
- Governance Company 有 skill/MCP registry v0。
- Learning Research Company 给出 memory architecture MVP 方案。
- Kimi Code ACP 完成 read-only smoke。
- claudeminmax 完成至少 2 类低成本任务试跑。

---

## 10. 停止线

出现以下情况立即停：

- 任何 agent 开始大范围扫仓库且没有 contract。
- runtime_allocator 再次成为主线阻塞。
- Finbot 输出交易建议或启动生产化系统搭建。
- 本地模型被用于 Paperclip 系统搭建任务，而不是 research-only benchmark。
- Planning 公司开始自动写 authority memory。
- 外部 skill 未审计就安装或激活。
- 大模型下载未确认。

---

## 11. 下一步建议

下一步不应继续写长研究报告。应该做一个最小 live seed：

1. 更新 Paperclip company role map。
2. 给 Planning / Finbot / Learning Research 建项目和 issue。
3. 每个公司只跑一个最小任务。
4. 我验收结果。
5. 再决定是否继续投资 runtime_allocator / memory stack / skill manager。
