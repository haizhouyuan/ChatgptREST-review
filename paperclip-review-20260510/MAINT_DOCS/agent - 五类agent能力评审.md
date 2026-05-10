---
title: "agent - 五类agent能力评审"
source: "https://chatgpt.com/g/g-p-69f991394b2481918191114a902d237e/c/69f96ff1-2d0c-8398-ae36-487a5254e103"
author:
published:
created: 2026-05-06
description: "ChatGPT is your AI chatbot for everyday use. Chat with the most advanced AI to explore ideas, solve problems, and learn faster."
tags:
  - "clippings"
---
\# planning 五类 agent 会话历史 Pro 评审请求 提交日期：2026-05-05 提交人：Claude (claude-kimi lane) 请求对象：ChatGPT Pro --- ## 背景 planning 项目（事业部规划与内部工具开发）自 2026-01 起，先后由 5 类 agent 并行/交替执行： | Agent | 类型 | planning sessions | 说明 | |---|---|---|---| | codex1 | Codex (OpenAI GPT-5) | 121 | 早期主力，大量 strategy\_plan | | codex2 | Codex (OpenAI GPT-5) | 76 | 后期主力，hermes/memory/chatgptrest 为主 | | codex-official | Codex 官方实例 | 55 | 旧实例，2026-04 后基本退役 | | claudegac | Claude (Anthropic) + GAC | 10 | 红队审查 / 两轮车 / 战略 | | claudeminimax | Claude (Anthropic) Minimax | 19 | 红队代码审查为主 | | antigravity | Gemini (Google) | 100 pb 文件 | 二进制，未做 cwd 过滤 | 总计 281 个 planning 相关 sessions（2026-01 ~ 2026-05）。 由于原始 rollout/jsonl 总量约 2.5GB，本包仅附： - \*\*analysis\_report.md\*\* — 结构化分析报告 - \*\*sessions\_analyzed.jsonl\*\* — 281 条 compact 元数据（agent / turns / topic / pushbacks / pitfalls） - \*\*README.md\*\* — 原始会话路径清单 - \*\*antigravity\_note.md\*\* — antigravity 格式说明 --- ## 核心问题 请先读 analysis\_report.md，然后基于 sessions\_analyzed.jsonl 的元数据和报告结论，回答以下问题： ### 1. 五类 agent 的能力画像 对 codex1 / codex2 / codex-official / claudegac / claudeminimax 各做一张能力画像： - 最擅长的任务类型 - 最薄弱的环节 - 与用户的协作模式（主动/被动、指令理解准确度、上下文保持） - 典型失败模式 ### 2. 用户最不满意的地方 从 pushback 样本和 pitfalls 分布中，识别用户最频繁的 5 类不满： - 每类不满的典型触发场景 - 受影响最多的 agent - 根因判断（是 agent 能力不足、任务定义不清、还是上下文/记忆问题？） ### 3. 项目演进的决策节点 从时间线和主题变迁中，识别 planning 项目的 5 个关键决策/转向节点： - 每个节点发生了什么 - 哪个 agent 主导的 - 决策质量如何（是否有后续 pushback 或返工） ### 4. 记忆系统与 agent 表现的关联 请把本分析与上一个评审请求（记忆系统研究包）关联起来： - 当前 session 历史中暴露的哪些 agent 问题，可以通过更强的记忆系统解决？ - 哪些问题是记忆系统解决不了的（需要架构/工作流/人机交互层面的改变）？ - 从 session 证据看，Graphiti（current truth / authority）或 MemPalace（verbatim）能缓解哪些具体问题？ ### 5. 如果重新组织 agent 协作 基于这些历史证据，如果你来重新设计 planning 项目的 agent 协作模式，你会怎么做？ - 哪些 agent 应该保留、合并、或淘汰？ - 任务分配规则（什么任务给谁） - 如何减少用户 pushback 和返工 - 记忆系统应该承担什么角色 ### 6. antigravity 的定位 antigravity 只有 100 个二进制.pb 文件，未能做文本分析。基于你对 Gemini / antigravity 的了解，它在 planning 项目中的合理定位是什么？应该承担什么类型的任务？ --- ## 输出格式
```
1. 一句话总判断
2. 五类 agent 能力画像（表格 + 每类 2-3 行说明）
3. 用户不满 Top 5（场景 + 根因 + 影响 agent）
4. 关键决策/转向节点 Top 5（时间 + 决策 + 主导 agent + 质量判断）
5. 记忆系统关联分析
6. 重新设计 agent 协作的建议
7. antigravity 定位建议
8. 给用户的 3 条立即行动建议
9. 反对意见 / 风险
```
\--- ## 操作要求 - 以附件中的本地事实为主 - 不要泛泛而谈，尽量引用数据（如 "codex2 的 hermes 主题从 5 个 session 激增到 33 个"） - 如果某些判断信息不足，请说"信息不足"，不要编造 - 如果与上一个记忆系统评审请求的结论冲突，请明确指出来 谢谢。

我会先解包并核对报告与 281 条元数据，按 agent、pushback、pitfalls、时间线和主题做交叉统计；同时对齐上一轮记忆系统评审的可用上下文，缺失处明确标注信息不足。

已读完报告和元数据，但其未逐轮全文标注；我会把 pushback 区分为硬约束/纠正与真实不满，并按证据强度分档。

## 1\. 一句话总判断

planning 的主要瓶颈不是“缺一个更聪明的 agent”，而是 **缺一个可审计的 current truth / authority / verbatim 记忆底座，以及按角色分工的 agent 工作流** ：codex2 已经承担了事实上的复杂工程主力，但长链返工和上下文漂移明显；Claude 两条 lane 更适合红队和独立审核；codex-official 基本应退役；antigravity 暂时不能作为事实证据源，只适合作为 IDE / UI / 多工作区探索型执行面。

口径说明：本判断主要基于 `analysis_report.md` 和 `sessions_analyzed.jsonl` 。但该包没有逐轮全文，只包含 compact metadata、pushback 样本和 pitfalls 信号；因此“pitfall”只能视为风险信号，不等同于真实失败。另一个重要更正是：本包显示 **整体 Hermes 主题从 2026-03 的 5 个 session 增至 2026-04 的 33 个 session** ；codex2 自身 Hermes 是 **3 月 5 个、4 月 13 个** ，不是 33 个。

---

## 2\. 五类 agent 能力画像

| Agent | 样本与主战场 | 最擅长任务类型 | 最薄弱环节 | 与用户协作模式 | 典型失败模式 |
| --- | --- | --- | --- | --- | --- |
| **codex1** | 121 sessions；99 个 strategy\_plan；总 turns 2246，平均 18，中位数 2 | 早期战略规划、结构化业务文档、会议/材料整理的初稿生成 | 会话短、上下文延续弱；复杂工程与多文件边界控制弱 | 用户强主导，codex1 多数时候像“执行短任务/生成草案” | very\_short\_session 85 次；容易需要用户补充“不要回退别人改动”“不要臆测说话人”“只处理负责文件”等硬边界 |
| **codex2** | 76 sessions；总 turns 25444，占全部 turns 约 86.5%；strategy\_plan 33、Hermes 18、codex\_infra 8、memory 4 | 复杂长链任务、Hermes / ChatgptREST / memory / infra 综合分析与实现推进 | 长链稳定性、当前代码现实与旧文档冲突处理、测试 lane / 成本 / 风控策略 | 用户与 codex2 高频迭代，codex2 是事实上的后期主力；用户经常中途校正方向 | 3k+ turns 的 Hermes / strategy 长会话伴随 error、回滚、failed、exception 等信号；被提醒“不要用 Pro 模型”“要看近期开发历史”“不要修改文件” |
| **codex-official** | 55 sessions；但其中 52 条按文件名与 codex1/codex2 重复，只有 3 条独立 Hermes 样本 | 旧 Codex 实例的冗余执行；独立能力证据不足 | 独立样本太少，无法形成可靠画像 | 不是稳定协作对象，更像历史遗留实例 | 与 codex1 高度重复导致统计污染；继续保留会制造口径混乱 |
| **claudegac** | 10 sessions；669 tool\_calls；Hermes 3、two\_wheeler 2，其余分散 | 独立红队、战略判断、架构争议仲裁、业务 authority 收口 | 样本少；需要用户给足事实包和审核边界；不适合作为日常实现主力 | “审核者 / 反方 / 顾问”模式明显，用户要求它直接挑错、冻结判断、指出不能冻结处 | 容易被用户反复约束“不要空谈架构”“以代码和真实运行证据为准”“不要继续大范围扫仓库” |
| **claudeminimax** | 19 sessions；409 tool\_calls；14 个 Hermes；平均 turns 3.8 | 短促、窄范围、高密度工具调用的红队代码审查 | 跨轮记忆弱；容易重复上一轮已修问题；对“当前最新代码”依赖强 | 用户给非常窄的 code review scope，要求只报 High / Medium findings | 用户反复强调“不重复已修问题”“只看当前最新代码”“没有 High/Medium 就只输出残余风险/测试缺口” |

### codex1

codex1 是早期 planning 的“文档与战略草案机”。121 个 session 中 99 个是 strategy\_plan，占 81.8%；这说明它非常多地服务于业务规划、内部报告、材料整理，而不是后期 Hermes 工程主线。

它的问题也很清楚：中位数 turns 只有 2，very\_short\_session 85 次，占 codex1 session 的约 70.2%。这不是单纯能力差，而是它在工作流中经常被当成一次性短任务执行器，导致上下文保持和长期决策承接天然不足。

典型失败不是“完全不会做”，而是 **缺少边界意识和事实保守性** ：会议精校里用户反复强调“不要回退别人改动”“只处理你负责的输出文件”“说话人不要臆测真实姓名”，说明 codex1 在协作项目里需要更强的任务 contract 和 verbatim 依据。

### codex2

codex2 是后期事实主力。它只有 76 个 session，但总 turns 25444，占全部 29412 turns 的约 86.5%；这说明真正复杂、长链、工程化的工作主要压在 codex2 上。

它的强项是能承接 Hermes、ChatgptREST、codex\_infra、memory 等交叉问题。Hermes 主题在 codex2 中有 18 个，其中 2026-03 有 5 个、2026-04 有 13 个；同时它还有 4 个 memory 主题 session，说明它已经承担“系统架构 + 记忆设计 + 实现验证”的混合角色。

它的薄弱点是 **长链任务容易形成高返工闭环** 。notable sessions 里 codex2 出现多个 3000+ turns 的超长 session，且伴随 error / 回滚 / failed / exception / 不对等信号。用户的 pushback 也多集中在“当前代码现实不是旧文档说的那样”“测试不要用 Pro 模型”“看近期开发历史”“不要改文件”等 current truth 与执行纪律问题。

### codex-official

codex-official 不应被当作独立强样本。按 `sessions_analyzed.jsonl` 的 basename 去重，codex-official 的 55 条里有 52 条与 codex1/codex2 重名，其中 50 条是 codex1 + codex-official 重复，2 条是 codex1 + codex2 + codex-official 三方重复；只有 3 条 2026-04-17 的 Hermes session 是独立样本。

所以它的画像结论应该很克制： **它不是一个值得继续单独投入的 agent lane，而是历史遗留/迁移期实例** 。如果继续保留，会把 session 统计、责任归因、成果归档都变得不干净。

### claudegac

claudegac 的特点是样本少但工具密度高：10 个 session、669 次 tool\_calls，平均每 session 66.9 次。它不是日常产线执行器，而是“独立审查 / 红队 / 战略顾问”。

它最有价值的场景包括 Hermes + ChatgptREST 架构红队、两轮车业务 authority 收口、planning / memory / Hermes 关系的独立审核。用户给它的任务经常是“不要站队 Codex 或 Antigravity”“哪些诊断可以冻结”“如果方向错要直接指出”，这说明它承担的是 **反共识、找盲区、冻结判断** 的角色。

弱点是它也需要很强的边界输入，否则会出现“空谈架构”风险。用户反复强调“以代码和真实运行证据为准”“不要继续大范围扫仓库”，说明 claudegac 最好被放在 **已整理事实包之后** ，而不是直接丢进整个仓库自由探索。

### claudeminimax

claudeminimax 是非常典型的窄范围代码红队。19 个 session 中 14 个是 Hermes，且 409 次 tool\_calls 分布在只有 73 个 turns 上，平均每 turn 约 5.6 次工具调用，说明它倾向于短对话、高工具密度、直接审代码。

它适合做“当前未提交改动”的 High / Medium 级别风险审查，尤其是状态机、并发、路径泄露、doneish recovery、authoritative/final contract、context/resolve、graph/query 等问题。

它的问题是跨轮记忆与去重。用户多次提醒“不要重复上一轮已经修掉的问题”“只看当前最新代码”“如果没有 High/Medium，只输出 Residual Risks / Testing Gaps”。这说明 claudeminimax 的最佳用法不是让它自由审，而是给它一个 **上一轮 findings ledger + 当前 diff + 已修项列表** 。

---

## 3\. 用户不满 Top 5

| 排名 | 不满类型 | 典型触发场景 | 受影响最多的 agent | 根因判断 |
| --- | --- | --- | --- | --- |
| 1 | **任务边界不清 / 越权修改 / 产物污染** | “把你的产物删掉”“不要修改任何文件”“不要改 ChatgptREST”“不要回退别人改动，只处理你负责的输出文件” | codex2、codex1、codex-official | 一半是 agent 执行纪律不足，一半是缺少工单级 write allowlist / stop line / repo ownership 机制 |
| 2 | **current truth 不稳，旧文档与代码现实冲突** | 用户纠正 “ChatgptREST 已经是多平面宿主，不是单一 OpenClaw 插件后端”；要求“看近期开发历史”“最关键文件与行号”“当前最稳判断” | codex2 最明显；claudegac / claudeminimax 也受影响 | 主要是上下文/记忆问题：没有权威 current truth 层，agent 会把旧文档、旧结论、当前代码混在一起 |
| 3 | **泛评、复述背景、输出不按审核格式** | “不要泛评”“不要复述背景”“不要写长文，给结构化结论”“只输出 findings”“没有 High/Medium 就明确写无” | claudegac、claudeminimax、codex2 | 人机交互/工作流问题：缺少固定 review schema 和验收格式；不是单靠模型能力能彻底解决 |
| 4 | **测试/模型 lane 使用不当，成本与风控意识不足** | “做 chatgptgptweb lane 测试不要用 Pro 模型”“不要用 smoke 问 ChatGPT 花很多时间，还会触发风控” | codex2 | 主要是工作流与策略记忆问题：需要把测试模型、禁用模型、风控路径写成可检索 policy，而不是靠用户临场提醒 |
| 5 | **事实保守性不足：ASR、说话人、claim、冻结/未证实边界容易漂** | “说话人不要臆测真实姓名”“对不确定词用全角方括号标记存疑”“claim\_ledger 下调为 gap”“哪些诊断可以冻结/不能冻结” | codex1、codex2、claudegac、claudeminimax | Graphiti 类 authority 记忆可以缓解一部分；但最终还需要 claim ledger、证据等级、只读复核、人工冻结机制 |

补充判断：pushback 数量不能简单等价为“用户最不满意程度”。例如 claudegac 有 7/10 个 session 带 pushback，但很多 pushback 本身是用户给红队任务的硬约束，不一定代表 agent 已经失败。真正要看的是 pushback 的语义：越是“不要改”“不要复述”“不要重复已修”“当前真实链路不是这样”，越能说明系统性问题。

---

## 4\. 关键决策 / 转向节点 Top 5

| 时间 | 决策 / 转向 | 主导 agent | 本地证据 | 质量判断 |
| --- | --- | --- | --- | --- |
| **2026-01** | planning 以 strategy\_plan 为主线，形成事业部规划和内部材料工作区 | codex1 + codex2 + codex-official | 1 月总 42 sessions，strategy\_plan 33；codex1 13、codex2 16、codex-official 13 | 方向成立，但过程还早期。codex1 / official 很多短会话，且 official 与 codex1 大量重复，说明协作边界不成熟 |
| **2026-02** | 从纯战略规划扩展到 ChatgptREST / codex\_infra / PPT / robot\_manufacturing 等内部工具与业务落地 | codex1 / codex2 / codex-official | 2 月总 83 sessions；strategy\_plan 52，chatgptrest 从 1 月 2 个增至 2 月 11 个，codex\_infra 7，ppt\_design 5，robot\_manufacturing 3 | 质量中等。出现“阶段门禁与停止线”“2026 样板项目闭环”等好口径，但也有“不要改 ChatgptREST”“最小改动”“把产物删掉”等边界 pushback |
| **2026-03-25 ~ 03-27** | meeting\_intel 从原始会议材料转向“语义精校 + speaker uncertainty + 可审计事实保留” | codex1 | codex1 在 3 月有 7 个 meeting\_intel session；其中一个 768 turns；随后多个 chunk 任务被要求“不臆测说话人”“保守纠偏 + 语义重组” | 决策方向正确，但初始执行需要强监督。用户反复重申不回退别人改动、只处理负责文件、不能丢事实，说明流程模板还没固化 |
| **2026-03-31 ~ 04-12** | 两轮车 / 车轮车身业务从“市场调研”转向“事业部筹建 + 多客户校准 + authority 收口” | claudegac | claudegac 两轮车 session 2 个；4 月 12 日 notable session 299 turns、479 tool\_calls；pushback 样本出现“0497 先保命，车轮必须成为独立装载主体的核心业务，车身……第二曲线” | 战略判断质量较高，但仍有关键未决项：例如“车轮要不要进入合资公司”。这类问题不能靠 agent 单独拍板，需要 authority + 决策会冻结 |
| **2026-03-29 ~ 04-20** | Hermes 成为主系统/前台，ChatgptREST 退到 automation kernel / 共享后端；同时开始重新定义 planning 的 memory / authority 角色 | codex2 主导，claudegac / claudeminimax 红队 | 整体 Hermes 主题从 3 月 5 个增至 4 月 33 个；4 月 Hermes 分布为 codex2 13、claudeminimax 14、claudegac 3、codex-official 3；codex2 有 2847-turn memory session | 这是最重要也最混乱的转向。方向上看是系统架构升级；执行上看返工重、错误信号密集、需要多轮红队。用户明确关心“记忆管理和上下文管理怎么做才效果最好”“planning 更像读写底座/数据库/业务记忆库，Hermes 才是主系统” |

---

## 5\. 记忆系统关联分析

这里有一个限制：我没有拿到“上一个记忆系统研究包”的原文，也没有从可用个人上下文中检索到该评审结论。因此我不能判断是否存在冲突；以下只基于本次包内证据，以及你在题目里给出的两条定义： **Graphiti = current truth / authority** ， **MemPalace = verbatim** 。

### 5.1 可以通过更强记忆系统缓解的问题

**第一类：current truth 漂移。**  
最典型证据是 codex2 被用户纠正 ChatgptREST 的真实架构：它已经是多平面宿主，不是单一 OpenClaw 插件后端；public MCP 是 `/v3/agent/turn` 的治理 wrapper，advisor\_v3 是另一条真实主链。这类问题非常适合 Graphiti：把“当前真实链路”“已废弃旧说法”“权威文件/代码路径”“冻结/未冻结状态”作为图谱事实，而不是让 agent 每次重新猜。

**第二类：跨轮红队重复与 stale finding。**  
claudeminimax 的 pushback 多次出现“不要重复上一轮已经修掉的问题”“只看当前最新代码”“没有 High/Medium 只输出 Residual Risks / Testing Gaps”。这类问题适合 MemPalace + finding ledger：MemPalace 保存上一轮原文 findings、用户纠正、已修证明；Graphiti 把 finding 状态投影为 open / fixed / waived / not-repro / still-risk。

**第三类：任务边界与仓库写权限。**  
“不要改 ChatgptREST”“不要修改任何文件”“不要回退别人改动”“只处理你负责的输出文件”这类指令不应只靠 prompt 记忆，而应进入任务 contract。Graphiti 可以维护 repo ownership、write allowlist、stop line；MemPalace 保存用户原始硬约束，供新 session preflight 注入。

**第四类：测试 lane 与模型使用策略。**  
codex2 被提醒“做 chatgptgptweb lane 测试不要用 Pro 模型”“不要用 smoke 触发风控”。这类规则应该成为可检索 policy：某个 lane 可用哪些模型、禁用哪些模型、哪些测试只能 dry-run、哪些必须 read-only。Graphiti 负责 current policy，MemPalace 负责保留原始用户提醒和上下文。

**第五类：业务 authority / claim ledger。**  
两轮车、机器人、会议纪要、claim\_ledger 中出现大量“可冻结/不能冻结/下调为 gap/未证实”的状态。这正是 Graphiti 的价值：把 claim、证据、来源、版本、决策状态、责任人连起来。MemPalace 则负责保存会议原文、用户纠正原文、ASR 原文和逐段精校原文，避免 agent 为了“通顺”而丢事实。

### 5.2 记忆系统解决不了的问题

**第一，真实架构缺陷解决不了。**  
例如 Hermes / ChatgptREST 里的状态机、doneish recovery、context/resolve 是否真正被 prompt 消费、graph/query metadata-only 是否进入 prompt、terminal push 是否污染 contract 等，记忆只能让 agent 知道问题，不能替代测试、代码修复、集成验收。

**第二，工作流不清解决不了。**  
如果一个任务没有明确 allowed files、read/write mode、验收标准、输出格式、停止线，再强的记忆也只是让 agent 更快地在错误方向上执行。

**第三，业务决策不能由记忆自动冻结。**  
例如“车轮是否进入合资公司”这类问题，Graphiti 可以列证据、列冲突、列未证实点，但不能替代你或决策会做取舍。

**第四，数据不可读问题解决不了。**  
antigravity 现在只有 100 个二进制 `.pb` ，且未做 cwd 过滤；这不是记忆系统问题，是 ingestion / protobuf 反序列化 / session indexing 问题。

### 5.3 Graphiti 与 MemPalace 各自最该承担的角色

| 系统 | 应承担角色 | 能缓解的本包具体问题 | 不该承担的角色 |
| --- | --- | --- | --- |
| **Graphiti** | current truth、authority、claim ledger、repo ownership、policy graph | ChatgptREST 真实链路纠偏；Hermes 是否唯一前台；planning 是记忆底座还是功能包；claim 冻结/gap；测试 lane 策略 | 不应保存大段原文；不应把未验证推断当事实 |
| **MemPalace** | verbatim、原始会议/用户纠正/红队 finding 原文、长文本可回放证据 | ASR 精校不丢事实；speaker 不臆测；红队不重复上一轮；用户原始 hard constraints 可回看 | 不应直接决定 current truth；不应让旧原文覆盖新 authority |
| **两者组合** | MemPalace 保留“原话”，Graphiti 投影“当前结论” | 解决“旧材料很多、口径漂、agent 不知道哪个是最新真相”的核心痛点 | 不能替代代码测试、业务拍板、agent 任务分工 |

---

## 6\. 重新设计 agent 协作的建议

### 6.1 保留、合并、淘汰

| 处理 | Agent | 理由 |
| --- | --- | --- |
| **保留为主力工程/系统 agent** | codex2 | 承担 86.5% turns，是 Hermes / ChatgptREST / memory / infra 的事实主力；但必须加任务 contract 和 authority preflight |
| **保留为战略/会议/文档初稿 agent** | codex1 | strategy\_plan 样本最多，适合业务材料、会议整理、规划草案；不建议负责复杂长链工程 |
| **淘汰或归档** | codex-official | 55 条里 52 条与其他 Codex 实例重名，独立证据只有 3 条；继续使用会污染责任与统计 |
| **保留为独立架构/战略红队** | claudegac | 适合在已有事实包后做“冻结/不能冻结/盲区/替代方案”判断 |
| **保留为窄范围代码红队** | claudeminimax | 适合只读审查当前 diff，输出 High / Medium findings；不适合作为长期上下文 owner |
| **暂列实验执行面** | antigravity | 只有 binary `.pb` ，不能纳入历史事实分析；可用于 IDE / browser / UI / 多工作区执行，但必须补可读导出与 cwd 过滤 |

### 6.2 任务分配规则

| 任务类型 | 首选 agent | 配套要求 |
| --- | --- | --- |
| Hermes / ChatgptREST / memory / codex\_infra 实现与综合诊断 | codex2 | 先跑 Graphiti current truth preflight；明确 write allowlist；输出 diff、测试、未决风险 |
| 业务战略报告、事业部规划、会议纪要精校 | codex1 | MemPalace 注入 verbatim；Graphiti 注入 authority；必须标注不确定与 gap |
| 架构争议、方向是否错、哪些结论可冻结 | claudegac | 只读；给它事实包、当前争议、候选方案；禁止大范围散扫 |
| 当前未提交改动红队代码审查 | claudeminimax | 给 diff、上一轮 findings ledger、已修项、只报 High / Medium；禁止重复旧问题 |
| UI 工作流、浏览器验证、多 workspace agent 编排 | antigravity | 只能作为 execution / visual validation lane；产物必须回写到可审计文本系统 |
| 旧实例验证 / 兼容性 | codex-official | 原则上不用；如必须用，只作为一次性对照，不进入主统计 |

### 6.3 减少 pushback 和返工的机制

每个 session 开始前生成一张 **任务 contract 卡** ：

```markdown
任务目标：
当前 authority：
verbatim 证据：
允许读取路径：
允许修改路径：
禁止修改路径：
模型 / 测试 lane：
输出格式：
验收命令：
停止线：
已知上一轮 findings：
本轮不能重复的内容：
```

每个 session 结束后写回两类记忆：

```markdown
Graphiti 写回：
- 新增/修改 current truth
- 冻结结论
- gap / unresolved
- repo ownership / policy
- finding 状态变化

MemPalace 写回：
- 用户原始纠正
- 关键会议原文
- 红队 finding 原文
- agent 输出摘要和关键证据片段
```

这样可以直接减少本包里最常见的 pushback：不要改错文件、不要泛评、不要重复已修问题、不要用错模型、不要把旧文档当当前真相。

### 6.4 推荐的执行流

**工程任务流：**

```markdown
Graphiti current truth preflight
→ codex2 实现 / 诊断
→ 本地测试与证据产物
→ claudeminimax 窄范围红队
→ codex2 修复
→ claudegac 只在架构争议未冻结时介入
→ Graphiti / MemPalace 写回
```

**业务/战略任务流：**

```markdown
MemPalace 拉取 verbatim
→ Graphiti 拉取 authority / claim ledger
→ codex1 出结构化初稿
→ claudegac 做冻结/盲区/反方审核
→ 用户决策
→ Graphiti 更新 current truth
```

---

## 7\. antigravity 定位建议

本包对 antigravity 的证据非常有限：只有 100 个二进制 `.pb` 文件，未做文本分析，也未做 cwd 过滤； `antigravity_note.md` 只说明原始路径和需要 protobuf 反序列化工具。因此， **antigravity 不应该参与本次五类 agent 的能力评分，也不应作为 planning 历史事实依据** 。

从产品定位看，Google 把 Antigravity 定义为 agentic development platform，强调 agent 可以跨 editor、terminal、browser 自主 plan / execute / verify，并提供 Editor View 与 Manager Surface；它还强调用 artifacts，如 task list、implementation plan、screenshots、browser recordings，来帮助用户验证 agent 工作，而不是只看 raw logs。 [Google Developers Blog](https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/) Google Cloud 的对比也把 Antigravity 定位为“complete agent manager and IDE experience”，而 Gemini CLI 更适合 terminal CLI 或 headless execution。 [Google Cloud](https://cloud.google.com/blog/topics/developers-practitioners/choosing-antigravity-or-gemini-cli)

所以在 planning 项目里，antigravity 的合理定位是：

| 适合承担 | 不适合承担 |
| --- | --- |
| UI / 前台体验验证 | 不能作为 authority 源 |
| Hermes workbench 的浏览器 walkthrough | 不能替代 Graphiti / MemPalace |
| 多 workspace agent 编排 | 不能在 `.pb` 不可读时参与审计 |
| 复杂 IDE 内重构、视觉反馈、截图证据 | 不适合处理业务 claim 冻结 |
| 长跑维护任务、bug reproduction、e2e smoke | 不适合无 cwd 过滤地混入 planning 统计 |

具体建议是：先做 antigravity ingestion，而不是先评价能力。

```markdown
1. protobuf 反序列化 .pb
2. 抽取 timestamp / cwd / repo / prompt / output / artifact
3. 做 cwd 过滤，只保留 /vol1/1000/projects/planning 相关会话
4. 生成 sessions_analyzed_antigravity.jsonl
5. 再与 codex2 / Claude lane 横向比较
```

在完成这些之前，antigravity 只能作为 **实验性执行面** ：可以让它跑 UI、浏览器验证、多工作区 IDE 任务，但最终结论必须回写到文本化、可审计的 planning 记忆系统。

---

## 8\. 给用户的 3 条立即行动建议

### 建议一：先清洗统计口径，尤其处理 codex-official 重复与 antigravity 不可读问题

当前 281 条里，codex-official 与 codex1/codex2 的重复会污染能力画像。建议立刻产出一个新索引：

```markdown
sessions_canonical.jsonl
字段：
- canonical_id
- agent
- original_file
- basename
- is_duplicate
- duplicate_group
- started_at
- cwd
- topic
- n_turns
- n_tool_calls
- pushback_count
- pitfall_count
- authority_refs
- write_paths
```

codex-official 的 52 条重复样本应从“能力比较”里剔除，只保留历史归档。antigravity 则先做 protobuf 反序列化和 cwd 过滤，未完成前不进入 agent ranking。

### 建议二：把 Graphiti / MemPalace 做成每个 session 的强制 preflight，而不是事后总结

每次 agent 开始工作前，先自动生成：

```markdown
current truth：
- Hermes 当前是否唯一前台
- ChatgptREST 当前真实角色
- planning 当前定位
- 当前有效 authority 文档
- 废弃/过期说法

verbatim：
- 用户最近 5 条硬纠正
- 相关会议原文片段
- 上一轮红队 findings
- 已修/未修列表
- 本任务禁止重复项
```

这会直接针对 codex2 的 current truth 漂移、claudeminimax 的重复旧 finding、codex1 的 ASR 事实保守性问题。

### 建议三：正式拆分四条 lane，停止“一个 agent 从头做到尾”

建议从现在开始只保留四条主 lane：

```markdown
codex2 = builder / systems integrator
codex1 = strategy / meeting / business draft
claudeminimax = narrow code red-team
claudegac = architecture / strategy red-team and freeze judge
```

每条 lane 必须有不同验收标准。codex2 的输出必须带测试和 diff；codex1 必须带 authority / gap 标注；claudeminimax 必须只报当前 High / Medium；claudegac 必须明确“冻结 / 不能冻结 / 盲区 / 下一步”。

codex-official 归档。antigravity 等可读导出完成后，再作为 IDE / browser / artifacts lane 接入。

---

## 9\. 反对意见 / 风险

**第一，compact metadata 不足以判定真实能力上限。**  
本包没有逐轮全文，很多 pushback 只是用户的新要求，不一定代表 agent 失败；pitfalls 又是关键词信号，尤其红队任务天然会包含 error、失败、exception 等词。

**第二，codex2 的错误信号可能被复杂任务放大。**  
codex2 承担了最难、最长、最核心的任务，所以它的 pushback 和 pitfalls 高，不必然说明它比其他 agent 差；更可能说明它是唯一被压到系统复杂度极限的 agent。

**第三，Claude 两条 lane 样本偏小。**  
claudegac 只有 10 个 session，claudeminimax 只有 19 个 session；虽然工具密度很高，但不能用它们的低 session 数直接推断长期稳定性。

**第四，Graphiti / MemPalace 也可能制造“错误权威”。**  
如果 current truth 没有版本、来源、过期机制，Graphiti 会把旧错结论固化得更快。authority 系统必须支持 supersede、deprecated、gap、conflict、needs-human-freeze。

**第五，agent 分工过细会增加协调成本。**  
如果没有自动 preflight、finding ledger、decision ledger，四条 lane 会变成四倍沟通成本。重组 agent 协作的前提是先把任务 contract 和记忆写回机制做扎实。

**第六，antigravity 不能靠印象纳入评审。**  
它产品定位上很适合 agent-first IDE、Manager Surface、browser / artifacts 验证，但当前 planning 包没有可读文本证据。没有 protobuf 解析和 cwd 过滤前，任何关于它在 planning 中真实表现的判断都属于信息不足。