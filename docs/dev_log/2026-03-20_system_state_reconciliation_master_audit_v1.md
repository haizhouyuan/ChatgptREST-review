# 2026-03-20 System State Reconciliation Master Audit v1

## 1. 文档定位

这份文档是截至 `2026-03-20` 的一次“状态对账型总盘点”。

目标不是重复此前几份 inventory，而是把它们与这几天的真实开发记录、当前运行状态、数据库实测和跨仓证据重新对齐，回答 5 个问题：

1. 当前系统到底哪些部分是真正在跑的。
2. 哪些能力是代码存在且最近刚修过的，不应再按旧认知理解。
3. 哪些盘点结论存在口径偏差或路径误判，需要显式勘误。
4. 当前有哪些并行真相源、边界冲突和残留过渡层。
5. 下一步做战略与实施计划时，应该以什么事实为准。

本报告优先级高于此前零散盘点中的“数值描述”，但不覆盖旧文档。
旧文档继续保留作为上下文与历史快照。

## 2. 本次对账范围与证据来源

### 2.1 代码与文档来源

本次对账交叉核对了以下文档与提交：

- [2026-03-19_codex_handoff_session_summary_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_codex_handoff_session_summary_v2.md)
- [2026-03-19_memory_kb_graph_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_memory_kb_graph_inventory_audit_v1.md)
- [2026-03-20_full_repo_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_full_repo_inventory_audit_v1.md)
- [2026-03-20_openclaw_finagent_cross_repo_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_openclaw_finagent_cross_repo_inventory_audit_v1.md)
- [2026-03-20_openclaw_runtime_history_and_cross_system_master_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_openclaw_runtime_history_and_cross_system_master_inventory_audit_v1.md)
- [2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_openmind_openclaw_work_orchestrator_strategy_blueprint_v3.md)
- [2026-03-16_model_routing_and_key_governance_blueprint_v1.md](/vol1/1000/projects/ChatgptREST/docs/2026-03-16_model_routing_and_key_governance_blueprint_v1.md)

最近几天代码提交线也做了交叉核对，重点覆盖：

- `2026-03-18` 到 `2026-03-20` 的修复、盘点、蓝图与 handoff 提交
- `public agent facade`
- `public MCP`
- `premium ingress strategist`
- `wait cancel`
- `cc-sessiond`
- `OpenClaw runtime`
- `memory / KB / graph`

### 2.2 运行态证据来源

本次补查的运行态证据包括：

- `systemctl --user list-units`
- `systemctl --user cat openclaw-gateway.service`
- `journalctl --user -u openclaw-gateway.service`
- `sqlite3 state/jobdb.sqlite3`
- `sqlite3 data/evomap_knowledge.db`
- `sqlite3 /home/yuanhaizhou/.home-codex-official/.openmind/*.db`
- `/home/yuanhaizhou/.home-codex-official/.openclaw/*`
- `/tmp/cc-sessions.db`
- `/tmp/artifacts/cc_sessions`

## 3. 本次对账后的顶层结论

### 3.1 当前真实系统不是单体，而是“四主两辅”

截至现在，真实运行面可以概括成：

- `OpenClaw`
  - 常驻 gateway
  - session/runtime/channel/cron/subagent 底座
- `ChatgptREST`
  - 当前最成熟的 durable execution + web driver + advisor/controller runtime host
- `OpenMind`
  - 作为系统身份和认知目标成立
  - 但当前大部分实际实现已经长在 `ChatgptREST` 内
- `Finagent`
  - 相对独立的投研垂直系统

辅线：

- `EvoMap`
  - 已是重数据底座，不再是空壳
- `cc-sessiond/team runtime`
  - 存在真实代码与历史实验资产
  - 但现在仍属于过渡层，不是当前主运行核心

### 3.2 现在的“主运行事实”

截至本次核实：

- `openclaw-gateway.service` 正在运行
- `chatgptrest-api / mcp / driver / workers / dashboard / feishu-ws / maint-daemon` 全部不在运行
- `state/jobdb.sqlite3` 与 `data/evomap_knowledge.db` 仍然是当前仓里最厚的 durable 状态资产
- `OpenClaw` 的用户态状态目录和安装版 runtime 仍在持续写入
- `OpenMind memory/KB` 当前运行态数据量非常小，和前一版盘点里的大数字不一致，必须勘误

### 3.3 当前最重要的规划前提

下一步做计划时，不应该再基于“系统缺很多能力”的假设，而应该基于下面这个更准确的判断：

- 能力很多已经存在
- 近期也修复了不少主链问题
- 真正的问题是：
  - 边界没收紧
  - 真相源不唯一
  - 路径解析与运行口径不统一
  - 有些子系统实际很弱，却在认知上被想象得很强

## 4. 对此前盘点的关键勘误

这一节是本次文档最重要的新增价值。

### 4.1 勘误一：OpenMind memory/KB 的 live 数据量此前被高估

[2026-03-19_memory_kb_graph_inventory_audit_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_memory_kb_graph_inventory_audit_v1.md) 中关于 memory/KB 的大规模 live 数字，本次必须降级为“待追源的旧口径”。

本次直接核实到的当前运行态路径是：

- `/home/yuanhaizhou/.home-codex-official/.openmind/memory.db`
- `/home/yuanhaizhou/.home-codex-official/.openmind/kb_registry.db`
- `/home/yuanhaizhou/.home-codex-official/.openmind/kb_search.db`
- `/home/yuanhaizhou/.home-codex-official/.openmind/kb_vectors.db`

当前实测结果：

#### memory.db

表结构不是 `memories`，而是 `memory_records`：

- `episodic = 2`
- `meta = 3`

也就是说，当前这套运行态 memory 不是“几千条 active memory”，而是只有 5 条记录。

#### kb_search.db

- `kb_fts_meta = 4`

#### kb_registry.db

- `artifacts = 2`
- `content_type = markdown` 仅 2 条

#### kb_vectors.db

- `vectors = 0`

结论：

- 当前正在被 OpenClaw gateway 通过 `HOME=/home/yuanhaizhou/.home-codex-official` 使用的这套 OpenMind memory/KB 数据非常小
- 前一版盘点中“memory/KB 很厚”的判断，不能再直接当成当前主运行面结论
- 下一步计划前，必须承认 `memory/KB` 与 `EvoMap` 之间存在明显的不对称

### 4.2 勘误二：EvoMap 很厚，但 OpenMind memory/KB 很薄

`data/evomap_knowledge.db` 本次重新核实后仍然成立：

- `documents = 7863`
- `episodes = 47857`
- `atoms = 99493`
- `evidence = 81210`
- `entities = 96`
- `edges = 90611`

因此，当前知识侧真实情况不是“memory + KB + graph 都已很厚”，而是：

- `EvoMap` 很厚
- `OpenMind memory/KB` 当前运行态很薄

这两者绝不能继续混说。

### 4.3 勘误三：OpenClaw 不是 repo-only，对象必须拆成三层

此前关于 “OpenClaw 到底是哪一版” 的争议，本次可以收敛。

当前真正的 OpenClaw 必须拆成三层：

1. 代码仓：
   [openclaw](/vol1/1000/projects/openclaw)
2. 用户态状态目录：
   [/home/yuanhaizhou/.home-codex-official/.openclaw](/home/yuanhaizhou/.home-codex-official/.openclaw)
3. 安装版运行时：
   `.../.local/share/openclaw-2026.3.7/node_modules/openclaw/...`

这三层缺一不可。

### 4.4 勘误四：3 月 19 handoff 的“服务全停”只对那个截面成立

[2026-03-19_codex_handoff_session_summary_v2.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-19_codex_handoff_session_summary_v2.md) 中关于“chatgptrest 相关服务全部停掉”的描述，对 `2026-03-19` 那个时间点成立。

截至本次核实：

- `chatgptrest-*` 服务当前仍然全部是 `inactive/dead`
- 但 `openclaw-gateway.service` 是 `active/running`

所以当前状态应该描述为：

- `ChatgptREST runtime lane` 处于停机静态状态
- `OpenClaw runtime lane` 处于持续运行状态

## 5. 2026-03-18 到 2026-03-20 的开发主线复核

### 5.1 这几天不是“只写了蓝图”，而是修了几条实链

最近几天已经落到代码和文档里的关键收口包括：

- `public agent facade` 合流和 runtime port 接线
- `public MCP` 只保留公共 surface
- `premium ingress` 的 `ask_contract / clarify / prompt_builder / post-review / EvoMap writeback`
- `premium strategist mainline`
- `public agent MCP durable recovery`
- `wait-phase cancel fast-terminalization`
- `cc-sessiond pool cleanup`
- `direct live ask containment`
- `prompt pollution containment`
- `synthetic/smoke fail-closed`

对应关键提交线：

- `085baf6`
- `9f5b274`
- `43d9b8c`
- `6b4a098`
- `0982598`
- `be4e8f3`
- `2a0f25a`
- `49041d0`
- `dba72b6`
- `e430e94`
- `0841b6d`

### 5.2 对当前状态的实际意义

这意味着：

- `public facade` 这条线已经不是概念稿
- `premium ingress strategist` 也不是未开工，而是主链已经补上
- `cc-sessiond` 已经被清理和收边，但仍不应当被重新抬成未来核心
- 当前真正缺的不是更多 patch，而是把这些已有收口重新放回正确架构边界里

## 6. 截至当前时点的运行态快照

### 6.1 systemd 服务

当前核实结果：

- `openclaw-gateway.service = active/running`
- 以下均为 `inactive/dead`：
  - `chatgptrest-api.service`
  - `chatgptrest-dashboard.service`
  - `chatgptrest-driver.service`
  - `chatgptrest-feishu-ws.service`
  - `chatgptrest-maint-daemon.service`
  - `chatgptrest-mcp.service`
  - `chatgptrest-worker-repair.service`
  - `chatgptrest-worker-send-chatgpt@1/2/3`
  - `chatgptrest-worker-send-gemini@1/2/3`
  - `chatgptrest-worker-wait.service`

相关 timer 当前也均为 `inactive/dead`，包括：

- `guardian`
- `health-probe`
- `ui-canary`
- `monitor-12h`
- `finbot-*`
- `issue-*`
- `viewer-watchdog`

### 6.2 OpenClaw gateway 运行配置

`openclaw-gateway.service` 当前非常关键的事实有 3 个：

1. 运行的是安装版 `OpenClaw Gateway (v2026.3.7)`
2. `HOME` 被 systemd 显式设为：
   - `/home/yuanhaizhou/.home-codex-official`
3. gateway 会加载：
   - `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`
   - `/vol1/maint/MAIN/secrets/credentials.env`

这说明：

- OpenClaw 已经与 ChatgptREST/OpenMind 的 env 绑定
- OpenClaw 现在不是纯独立系统，而是现实中的跨系统常驻运行底座

### 6.3 OpenClaw gateway 当前 live 异常

近端日志里最稳定复现的问题是：

- `openmind-telemetry: flush failed: TypeError: fetch failed`

而不是飞书入口完全挂掉。

这意味着：

- OpenClaw 主 gateway 仍在跑
- 但它和 OpenMind telemetry/ingest 之间有持续失败
- 这已经是当前最明确的 live integration defect 之一

## 7. 当前 durable 状态资产盘点

### 7.1 ChatgptREST job/controller ledger

`state/jobdb.sqlite3` 当前仍是最厚、最真实的 durable ledger：

- `jobs = 7924`
- `job_events = 1481412`
- `advisor_runs = 201`
- `advisor_steps = 507`
- `controller_runs = 130`
- `controller_work_items = 436`
- `controller_artifacts = 63`
- `client_issues = 386`
- `incidents = 6055`

状态分布：

- `completed = 6989`
- `error = 623`
- `canceled = 276`
- `in_progress = 15`
- `queued = 14`
- `needs_followup = 6`
- `cooldown = 1`

Top job kinds：

- `repair.check = 3186`
- `chatgpt_web.ask = 2795`
- `gemini_web.ask = 1098`
- `repair.autofix = 539`
- `gemini_web.generate_image = 120`
- `chatgpt_web.extract_answer = 57`
- `qwen_web.ask = 37`

结论：

- 即使当前服务停着，仓里最成熟的 durable 执行账本仍是 `jobdb`
- 这个数据库已经不只是 job queue，而是 advisor/controller/issues/incidents 的复合 ledger

### 7.2 EvoMap knowledge ledger

`data/evomap_knowledge.db` 仍是当前最厚的知识资产。

这说明：

- EvoMap 是真知识底座
- 它不是未来式
- 但它与当前很薄的 OpenMind memory/KB 之间存在明显脱节

### 7.3 OpenMind memory/KB

当前运行态很小：

- memory records = 5
- kb FTS docs = 4
- kb registry artifacts = 2
- kb vectors = 0

因此本次对账后的判断是：

- `OpenMind memory/KB` 代码存在
- runtime 可加载
- 但当前这套用户态运行面并没有形成厚数据资产

### 7.4 cc-sessiond 现状

当前 `/tmp/cc-sessions.db` 没有可读的活跃 session 分布输出。

但 `/tmp/artifacts/cc_sessions` 下仍有 `11` 个 artifact 目录。

结论：

- `cc-sessiond` 当前更像历史/过渡运行残留
- 不是当前主运行心脏
- 但也不是完全空，因为 artifact 证据还在

## 8. 分模块状态总表

### 8.1 ChatgptREST core job + web driver

状态判断：

- 代码成熟度：高
- durable 状态：高
- 当前服务活跃度：低
- 战略重要性：高

解释：

- 这块不是废弃物
- 是当前最厚的 execution substrate 之一
- 但现在不在常驻运行

### 8.2 Advisor / OpenMind runtime in ChatgptREST

状态判断：

- 代码成熟度：中高
- 主链修复状态：近期有显著收口
- durable 状态：已有 ledger
- 当前服务活跃度：停机
- 战略重要性：高

解释：

- 不是纯蓝图
- 真实运行主链已经做出 `AskContract -> AskStrategyPlan -> clarify -> compiled prompt -> controller`
- 但当前服务没有起

### 8.3 public agent facade / public MCP

状态判断：

- 代码成熟度：中高
- 主链状态：近期刚修过
- 当前运行活跃度：停机
- 战略重要性：高

解释：

- 这块已经不该再按“老 MCP 裸工具集合”理解
- 已经有清晰公共 surface 和 durable recovery 修复

### 8.4 premium ingress strategist

状态判断：

- 代码成熟度：中
- 主链状态：已接通
- 残留风险：仍需 live 验收
- 战略重要性：高

解释：

- 不能再说“strategist 还没做”
- 正确说法是“主链已接通，但还需要重新放回长期架构边界里”

### 8.5 model routing

状态判断：

- 代码成熟度：中高
- 当前一致性：低
- 战略重要性：高

当前事实：

- 至少并存 `preset_recommender`
- `RoutingFabric`
- `ModelRouter`
- `routing_engine`
- `LLMConnector` 内的二次选择

当前最重要结论：

- 模型路由不是没做
- 而是做了多套
- 且“声明上的 winner”和“真实执行的 winner”仍可能不一致

这块仍然是下一步计划里的一级治理项。

### 8.6 memory / KB / graph

状态判断：

- `memory`: 代码有，当前 live data 很薄
- `KB`: 代码有，当前 live data 很薄
- `EvoMap`: 数据很厚
- `图库`: 仍然缺位

这块最重要的对账结论是：

- 不能继续笼统说“知识底座已经都做厚了”
- 更准确的说法是：
  - `EvoMap` 厚
  - `memory/KB` 当前 runtime 薄
  - `图库` 仍弱

### 8.7 controller / team / cc-sessiond

状态判断：

- controller ledger：真实存在
- team control plane：实验资产
- `cc-sessiond`：过渡层

结论：

- 这块不该被抹掉
- 但也不该再被抬成未来架构中心

### 8.8 OpenClaw

状态判断：

- 当前常驻运行核心：是
- 角色：gateway/session/runtime substrate
- 是否认知核心：否
- 战略重要性：极高

更准确的定位：

- 不是入口壳
- 也不是知识治理核心
- 而是当前唯一持续在线、持续执行、持续保有 session/channel continuity 的运行底座

### 8.9 Finagent

状态判断：

- 仍应视为垂直独立系统
- 不该拿它来反向定义主系统架构

### 8.10 Ops / automation

状态判断：

- 代码规模大
- 系统化程度高
- 但当前多数组件不在运行

结论：

- ops 不是附属脚本堆
- 已经是一层单独平台
- 但当前运行面处于“配置可启、服务未起”的静态状态

## 9. 当前最大的结构冲突

### 9.1 真相源并行

当前至少存在以下并行真相源：

- job ledger：`state/jobdb.sqlite3`
- OpenClaw session truth：`~/.openclaw/agents/*/sessions/sessions.json`
- EvoMap knowledge db：`data/evomap_knowledge.db`
- OpenMind memory/KB：`~/.home-codex-official/.openmind/*`
- dashboard/control-plane projection

### 9.2 路由 authority 并行

当前至少存在：

- OpenClaw agent config 路由
- `RoutingFabric`
- `ModelRouter`
- `routing_engine`
- `LLMConnector` fallback map
- advisor route/preset 层

### 9.3 认知层与执行层边界不清

当前最容易继续长歪的地方：

- OpenClaw 太容易被误当成大脑
- ChatgptREST 太容易被误当成未来总中台
- OpenMind 太容易和 ChatgptREST 代码现实脱钩
- `cc-sessiond/team runtime` 太容易被误抬成架构中心

### 9.4 数据层不对称

这次对账后最重要的事实之一：

- `EvoMap` 数据量极大
- `memory/KB` 当前 live 数据极小

这说明当前“知识系统”不是一个均衡体系，而是明显偏向 graph/document ingestion。

## 10. 下一步做计划前必须承认的事实

1. `OpenClaw` 必须被当作主运行底座对待，而不是入口壳。
2. `ChatgptREST` 当前仍是最成熟的 slow-path runtime host，但不该继续被想象成未来总中台。
3. `OpenMind` 目前更像系统身份和目标架构，而不是独立实现仓。
4. `public agent facade / premium ingress strategist` 这条线已经做出不少真实收口，计划不能再假设它们还是空白。
5. `model routing` 是结构性治理问题，不是缺一个函数。
6. `memory/KB` 当前 live 状态比之前以为的弱很多，必须在计划里修正预期。
7. `EvoMap` 是当前最厚的数据资产之一，后续计划必须明确它到底做 authority、projection 还是 recall substrate。
8. `cc-sessiond` 与旧 team runtime 应按实验资产/过渡层处理，而不是未来中心。

## 11. 作为下一步规划输入的优先级结论

如果下一步要进入正式规划，这份对账后我认为最可信的优先级输入是：

### P0

- 明确 `OpenClaw / ChatgptREST / OpenMind / Finagent` 的边界和 authority
- 明确模型路由唯一 authority
- 明确知识层 authority，尤其要正面处理 `EvoMap` 与 `memory/KB` 的不对称

### P1

- 明确 `planning / research` 两个主场景的前门对象模型
- 明确 `public agent facade` 与 `OpenClaw plugin` 的长期接法
- 明确 `OpenClaw telemetry flush failed` 的 live defect 是否要先修

### P2

- 再决定 `Work Orchestrator` 是逻辑层、插件层，还是独立服务
- 再决定 team runtime/skill system 的抽象深度

## 12. 最终判断

本次对账之后，系统的真实状态可以压缩成一句话：

**你现在拥有的不是一个缺能力的空系统，而是一组能力很强但边界错位、状态口径不统一、部分认知被高估的系统组合。**

更具体一点：

- `OpenClaw` 被低估了
- `EvoMap` 被低估了
- `memory/KB` 当前运行态被高估了
- `cc-sessiond/team runtime` 的中心性被高估了
- `public agent / strategist` 的完成度也被低估了

这份文档之后，下一步就不该继续做“摸黑补系统”，而应该基于这些已对账事实进入正式规划。
