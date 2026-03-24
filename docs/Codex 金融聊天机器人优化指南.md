# 基于 OpenAI Codex SDK 与 ChatGPT Pro 订阅构建零边际成本 FinChat 系统的深度架构研究报告

## 1. 执行摘要：金融对话系统的代理化与经济性重构

在当今的金融科技（FinTech）领域，对话式人工智能（Conversational AI）正在经历从基于规则的简单问答机器人向具备深度推理、自主工具调用能力的“智能代理”（Agentic AI）转型的关键时刻。传统的金融聊天机器人往往受限于预定义的意图识别和昂贵的按 Token 计费模式，这在处理高频、长上下文的金融分析任务时，不仅成本高昂，且缺乏深度推理能力。本报告旨在详尽阐述如何利用 **OpenAI Codex SDK** 构建一个名为 **FinChat** 的企业级金融分析系统，其核心战略在于通过复用 **ChatGPT Pro 会员订阅（Plus/Team/Pro）** 的鉴权机制，实现对底层大语言模型（LLM）能力的调用，从而将模型推理的边际成本降至接近于零。

本研究的核心价值在于打破了“高性能 AI = 高昂 API 成本”的固有公式。通过深入解构 Codex SDK 的 **二进制封装架构（Binary Wrapper Architecture）** 和 **模型上下文协议（Model Context Protocol, MCP）**，我们展示了如何将一个本地运行的 CLI 工具转化为一个高性能的 WebSocket 后端服务。FinChat 系统不仅能够通过 **Yahoo Finance MCP** 获取实时市场数据，利用 **Zod** 模式定义实现确定性的结构化财务报表输出，还能利用 **GPT-5.2-Codex** 独有的 **原生上下文压缩（Native Context Compaction）** 技术处理长达数万字的 10-K 财报文件。

报告将从底层运行时架构、零成本鉴权工程、MCP 金融数据生态集成、结构化输出控制以及前端流式交互体验五个维度进行全方位的技术解构，为构建下一代低成本、高智能的金融终端提供详实的工程蓝图。

## 2. 架构基石：Codex SDK 的二进制封装与运行时原理

要理解 FinChat 如何在不消耗 API 额度的情况下运行，首先必须透彻剖析 Codex SDK 的独特设计。与传统的 Python openai 库不同，Codex SDK 并非直接向 OpenAI 的 REST API 发起 HTTP 请求，而是一个通过标准输入输出（Stdio）与底层二进制文件通信的编排层。

### 2.1 二进制封装模式（Binary Wrapper Pattern）的深度解析

Codex SDK（无论是 TypeScript、Python 还是 Elixir 版本）在本质上是一个轻量级的语言绑定（Binding），其核心智能与业务逻辑驻留在一个名为 codex-rs 的高性能 Rust 二进制可执行文件中 1。这种架构设计对于金融应用而言至关重要，原因有三：

首先，**内存安全与计算效率**。金融数据的处理往往涉及大规模的 JSON 解析、历史行情数据的差异比对（Diffing）以及复杂上下文的索引构建。Rust 语言在内存管理上的零开销抽象（Zero-cost Abstractions）特性，确保了 codex-rs 在处理 GB 级别的金融文档或高频市场数据流时，不会引入 Node.js 或 Python 运行时常见的垃圾回收（GC）停顿，从而保证了 FinChat 系统在实时对话中的低延迟响应 1。

其次，**进程隔离与崩溃恢复**。在 FinChat 的架构中，每个用户会话（Session）或线程（Thread）实际上对应着操作系统层面的一个独立子进程。这种设计提供了天然的沙箱隔离。假设某个极其复杂的 PDF 财报解析任务导致代理进程崩溃，主应用程序（Host Application）可以捕获该异常并迅速重启代理，而不会导致整个 WebSocket 服务器瘫痪 1。对于金融服务而言，这种高可用性是不可妥协的。

最后，**跨语言与跨平台的一致性**。Codex SDK 的这种设计确保了无论开发者使用何种上层语言构建 FinChat 的后端（例如使用 TypeScript 结合 NestJS，或 Python 结合 FastAPI），底层的沙箱策略、鉴权逻辑和 MCP 协议解析行为都保持严格一致。这为团队在不同技术栈之间迁移或协作提供了坚实的基础。

### 2.2 JSONL 事件流协议与全双工通信

FinChat 系统与 Codex 代理之间的交互并非基于简单的“请求-响应”模型，而是基于 **JSON Lines (JSONL)** 的流式事件协议 1。SDK 通过标准输入（Stdin）将用户的金融查询（Prompt）和 MCP 工具的执行结果（Tool Outputs）序列化后发送给 codex-rs 进程；反之，代理通过标准输出（Stdout）实时推送一系列细粒度的事件对象。

这种通信机制是实现 FinChat 高级交互体验的核心。如下表所示，不同的事件类型承载了金融分析过程中的不同维度的信息：

| **事件类型标识 (Event Type)** | **事件描述与金融场景应用** | **数据载荷特征 (Payload)** |
| --- | --- | --- |
| turn.started | 标志着一次金融咨询回合的开始。在 UI 上，这通常触发“对方正在输入”的指示器。 | turn_id, created_at |
| reasoning.delta | **关键特性**。代理内部思维链（Chain of Thought）的增量输出。在 FinChat 中，这用于实时展示 AI 的分析路径，例如“正在计算 AAPL 的 20 日波动率...”或“检测到异常交易量...”，增强用户信任感。 | delta, snapshot |
| item.created | 代理决定调用外部金融工具。例如，代理决定查询 Yahoo Finance API。UI 可据此显示“正在连接市场数据源...”。 | tool_call_id, tool_name |
| item.completed | 工具执行完毕并返回结果。如果返回的是结构化的财务报表，后端可以将其缓存，用于生成独立的图表，而不必等待 AI 的文本解释。 | result, status (success/failure) |
| file_change | 如果任务涉及生成 Excel 或 PDF 报告，此事件会携带文件系统的差异（Diff）信息。 | path, diff |
| message.delta | 最终呈现给用户的自然语言回复片段。 | content, role |
| turn.completed | 回合结束。包含 Token 消耗统计，用于监控系统负载。 | usage, duration_ms |

通过监听并处理这些事件，FinChat 的后端可以构建一个高度动态的 WebSocket 服务，将 AI 的“思考过程”可视化，这是区别于传统黑盒式 AI 聊天机器人的关键竞争优势 1。

### 2.3 线程持久化与长程上下文管理

在金融咨询场景中，上下文的连续性至关重要。用户可能会先问“特斯拉现在的股价是多少？”，接着问“这与其 52 周高点相比如何？”。Codex SDK 的 **线程（Thread）** 机制通过本地文件系统（默认路径 ~/.codex/sessions）实现了会话状态的持久化 1。

这意味着 FinChat 的后端不需要维护复杂的向量数据库来存储短期对话历史。SDK 自动管理对话的序列化与反序列化。当用户在数小时甚至数天后重返 FinChat 时，系统只需调用 resumeThread(threadId)，即可瞬间恢复之前的分析上下文。对于使用 ChatGPT Pro 账号的用户来说，这种本地持久化策略避免了每次交互都重新上传整个历史上下文到 API，从而极大降低了潜在的速率限制风险，并提升了响应速度。

## 3. 零成本鉴权工程：基于 ChatGPT Pro 的 Headless 认证策略

本项目的核心经济逻辑在于利用 ChatGPT Pro 会员资格替代昂贵的 Token 计费 API。然而，Codex CLI 默认设计的 codex login 流程依赖于浏览器交互，这给在服务器（Headless）环境中部署 FinChat 后端带来了巨大的挑战。本章将详细阐述如何通过“凭证移植”技术突破这一限制。

### 3.1 鉴权机制逆向分析与 auth.json 结构

当用户在本地机器上运行 codex login 时，CLI 会启动一个本地 Web 服务器（通常监听 1455 端口），并引导用户在浏览器中完成 OAuth 2.0 认证流程。认证成功后，Codex 会生成一个包含访问令牌（Access Token）和刷新令牌（Refresh Token）的 JSON 文件，通常位于 ~/.codex/auth.json 3。

这个 auth.json 文件是 FinChat 系统能够“免费”运行的关键。它实际上是一个长效的凭证存储库，包含了代表用户 ChatGPT Pro 身份的加密令牌。研究表明，该文件并非与生成它的硬件物理绑定，这意味着它具有 **可移植性（Portability）** 5。

### 3.2 服务器端“无头”部署方案

要在没有图形界面的 Linux 服务器或 Docker 容器中运行 FinChat 后端，我们必须绕过浏览器登录环节。根据社区的最佳实践和技术文档，存在两种主要的技术路径：

#### 3.2.1 方案 A：SSH 隧道端口转发（SSH Tunneling）

这是一种即时认证的方法，适用于初次设置服务器环境。

1. **建立隧道**：在本地开发机上，通过 SSH 建立一个反向隧道，将远程服务器的 1455 端口映射到本地的 1455 端口。 Bash ssh -N -L 1455:127.0.0.1:1455 user@remote-finchat-server
1. **远程触发**：在远程服务器上运行 codex login。CLI 会提示用户打开 http://localhost:1455。
1. **本地验证**：用户在本地浏览器中打开该链接。由于端口转发的存在，认证回调（Callback）会被安全地传输回远程服务器的 CLI 进程，从而在远程生成 auth.json 5。
#### 3.2.2 方案 B：凭证文件移植（Credential Injection）

这是最适合 Docker 化部署和持续集成（CI/CD）的方案。

1. **本地生成**：开发者在本地机器上完成 codex login，确保 ~/.codex/auth.json 生成且有效。
1. **文件注入**：将该文件复制到服务器的目标目录，或者在 Docker 启动时将其作为卷（Volume）挂载。
  - **Docker 挂载示例**： YAML *volumes:* *-./secrets/auth.json:/root/.codex/auth.json:ro*
  - **SCP 传输示例**： Bash scp ~/.codex/auth.json user@finchat-server:~/.codex/auth.json
这种方法完全规避了服务器端的交互式登录需求，使得 FinChat 后端可以作为守护进程（Daemon）自动启动 5。

### 3.3 会话保活与自动刷新机制

虽然 auth.json 包含刷新令牌，但在长期运行的服务器环境中，令牌可能会因为超时或会话失效而过期。在桌面环境中，CLI 会尝试自动刷新或提示用户重新登录，但在 Headless 环境中，这可能导致服务中断。

为了确保 FinChat 的高可用性，建议实现一套 **凭证轮换机制（Credential Rotation Strategy）** 7。开发者可以在本地维护一个自动化脚本（可能结合 Puppeteer 等浏览器自动化工具，尽管 MFA 会增加难度），或者定期（如每周）手动执行登录并自动将新的 auth.json 推送到生产服务器。此外，FinChat 后端应当具备监控 401 Unauthorized 错误的能力，一旦检测到凭证失效，立即触发报警通知管理员介入。

### 3.4 速率限制与模型调度策略

尽管使用了包月订阅，OpenAI 对 ChatGPT Pro 账号仍设有“公平使用”原则下的速率限制（Rate Limits），例如每 3 小时 50 条消息（具体取决于模型版本如 GPT-4 或 GPT-5.2）。在 FinChat 架构中，如果多个用户共享同一个后端实例，极易触发此限制 8。

**架构优化建议：**

1. **模型分级调度（Model Triage）**：在 config.toml 中，将默认模型设置为较轻量级的 gpt-5.1-codex-mini。对于简单的行情查询（如“AAPL 现价”），使用 Mini 模型处理，既快又节省额度。
1. **按需升级**：仅当用户提出复杂推理需求（如“分析这份财报的潜在风险”）时，才在代码中动态覆盖配置，切换调用 gpt-5.2-codex 模型。 TypeScript *// TypeScript SDK 动态模型切换示例* *await* thread.run({ *prompt*: complexPrompt, *model_reasoning_effort*: *"high"* *// 仅在关键时刻消耗高级推理算力* });
这种混合模型策略能最大化利用 Pro 会员的资源，延缓速率限制的触发时间 1。

## 4. 金融数据中枢：基于 MCP 的数据源集成架构

一个没有实时数据的金融聊天机器人仅仅是一个只会产生幻觉的文本生成器。**模型上下文协议（Model Context Protocol, MCP）** 的引入，彻底解决了大模型与私有/实时数据连接的标准化问题，被誉为“AI 的 USB-C 接口” 1。对于 FinChat 项目，MCP 是连接 Codex 智能大脑与 Yahoo Finance 等金融数据源的神经中枢。

### 4.1 Codex 作为 MCP 客户端的配置

Codex SDK 内置了 MCP 客户端功能。我们无需编写复杂的 API 请求代码，只需在 ~/.codex/config.toml 配置文件中注册相应的 MCP 服务器，Codex 代理就能自动感知并调用这些工具。

在 FinChat 架构中，我们推荐配置两类 MCP 服务器以覆盖不同的数据需求：

1. **Yahoo Finance MCP Server**：用于获取实时股价、历史 K 线数据、期权链以及即时新闻。
1. **Financial Datasets MCP Server**：用于获取更深度的基本面数据，如资产负债表、利润表和现金流量表。
### 4.2 Yahoo Finance MCP 服务器的深度集成

社区已经提供了成熟的 Yahoo Finance MCP 实现（如 yahoo-finance-server 或 mcp-yahoo-finance），这些实现通常基于 yfinance Python 库 10。

config.toml 配置实战：

为了确保环境隔离，我们推荐使用 uvx（来自 Astral 的 Python 工具链）来运行这些服务器，避免依赖冲突。

```toml
[mcp_servers.yahoo_finance]
command = "uvx"
args = ["yahoo-finance-server"]
```

一旦配置生效，Codex 代理将自动获得以下核心工具能力 12：

- get_stock_price(symbol: str): 获取毫秒级实时报价。
- get_company_info(symbol: str): 获取公司概况、行业分类及主要竞争对手。
- get_historical_prices(symbol: str, period: str, interval: str): 获取指定时间窗口的 OHLCV 数据，支持 JSON 格式返回，便于前端绘图。
- get_financials(symbol: str): 拉取年度或季度的财务报表数据。
### 4.3 安全治理：只读模式与工具过滤

在金融领域，**“最小权限原则”（Principle of Least Privilege）** 是设计系统的红线。虽然目前的 Yahoo Finance MCP 主要是只读的，但如果未来 FinChat 集成了券商交易接口（如 Alpaca 或 Interactive Brokers），防止 AI 幻觉导致的意外下单（Fat Finger Error）就显得至关重要。

Codex SDK 提供了强大的 **工具过滤（Tool Filtering）** 机制。我们可以在配置中明确禁用任何涉及写入或交易操作的工具 1。

**安全配置示例：**

```toml
[mcp_servers.brokerage]
command = "uvx"
args = ["alpaca-mcp-server"]
# 严厉禁止下单、撤单和提现操作，仅允许查询账户和持仓
disabled_tools = ["place_order", "cancel_order", "withdraw_funds", "modify_position"]
```

通过这种配置，FinChat 代理被严格限制在“投资分析师”的角色，而非“交易员”，从架构层面消除了资金风险。

## 5. 深度文档智能：原生上下文压缩与 10-K 财报分析

金融分析的核心往往在于对长文档（如 10-K 年报、10-Q 季报、财报电话会议记录）的深度解读。传统的 RAG（检索增强生成）技术在处理此类任务时，往往通过切片（Chunking）破坏了文档的语义连贯性，导致无法回答跨段落的复杂逻辑问题。FinChat 将利用 GPT-5.2-Codex 的 **原生上下文压缩（Native Context Compaction）** 技术突破这一瓶颈。

### 5.1 原生上下文压缩：超越 RAG 的记忆机制

GPT-5.2-Codex 引入了一种类人的记忆机制，能够对历史交互和长文本进行语义级的压缩。它不是简单地丢弃旧 Token，而是将中间的推理过程、冗余信息进行“摘要化”存储，同时保留核心的架构决策和关键数据快照 14。

这使得 FinChat 能够一次性摄入长达数万字的财报文件，并保持长达 24 小时以上的有效上下文记忆。用户可以针对财报的细微末节进行多轮追问，例如“第 45 页提到的法律诉讼风险与第 12 页的营收下滑指引有何关联？”，这是传统切片式 RAG 难以做到的。

### 5.2 PDF 文档解析与加载方案

虽然 Codex 本身处理文本能力极强，但在读取 PDF 二进制文件方面，仍需借助工具。我们需要配置一个专门的 **PDF Reader MCP Server** 来辅助文档摄入 15。

**集成工作流：**

1. **用户上传**：用户在 FinChat 前端上传 NVDA_2024_10K.pdf。
1. **MCP 读取**：后端调用 pdf-reader-mcp 工具，将 PDF 内容转换为纯文本或 Markdown 格式。
1. **全量注入**：将转换后的全量文本直接注入 Codex 的当前线程上下文。
1. **压缩与推理**：GPT-5.2-Codex 自动触发上下文压缩机制，建立文档的内部语义索引。
1. **深度交互**：用户开始基于全文档进行问答。
**配置示例：**

```toml
[mcp_servers.pdf_reader]
command = "docker"
args = ["run", "-i", "--rm", "-v", "/local/pdf/path:/pdfs", "mcp/pdf-reader"]
```

使用 Docker 运行 PDF 解析器还能有效防止恶意 PDF 文件利用解析库漏洞攻击宿主机，进一步增强了系统的安全性 16。

## 6. 确定性金融输出：Zod 模式验证与结构化数据

金融用户不仅需要定性的文本分析，更需要定量的结构化数据以便于图表展示和进一步分析。然而，LLM 本质上是概率模型，容易产生格式不稳定的输出。FinChat 利用 Codex SDK 的 **结构化输出（Structured Outputs）** 功能，结合 **Zod** 模式定义库，强制模型输出符合严格类型定义的 JSON 数据 1。

### 6.1 定义金融数据契约

在 TypeScript 后端中，我们可以定义一套严谨的 Zod Schema 来描述各种金融对象。

**股票快照 Schema 定义：**

```typescript
import { z } from "zod";

const StockSnapshotSchema = z.object({
  symbol: z.string().describe("股票代码，如 AAPL"),
  marketData: z.object({
    price: z.number().positive(),
    changePercent: z.number(),
    volume: z.number().int().nonnegative(),
    peRatio: z.number().nullable().describe("市盈率，亏损公司可能为空")
  }),
  analysis: z.object({
    sentiment: z.enum().describe("AI 基于新闻的综合情绪判断"),
    riskFactors: z.array(z.string()).describe("列出主要的 3 个风险点"),
    summary: z.string().describe("简明扼要的 50 字行情总结")
  })
});
```

### 6.2 强制执行与错误免疫

在调用 SDK 的 thread.run() 方法时，通过传入 output_schema: StockSnapshotSchema 参数，我们实际上是将这个 Zod 对象转换为了底层的 JSON Schema，并注入到模型的系统提示词中。Codex 代理会自我修正其输出，直到完全符合 Schema 定义为止。

这意味着 FinChat 的后端接口返回给前端的数据是 **类型安全（Type-Safe）** 的。前端组件（如 React Recharts 图表库）可以直接消费这些数据进行渲染，而无需编写大量的防御性代码来处理 LLM 可能输出的错误格式（如缺少字段、类型错误等）。这使得 FinChat 从一个单纯的聊天窗口进化为一个能够生成动态仪表盘的智能终端。

## 7. 前端交互体验：流式响应与“思考”可视化

为了打造媲美专业金融终端的用户体验，FinChat 的前端必须充分利用 Codex SDK 提供的流式能力，将 AI 复杂的后台处理过程透明化。

### 7.1 实时思维链（Chain of Thought）展示

在处理复杂的金融分析任务时（例如“比较比特币与黄金在过去十年的抗通胀能力”），模型可能需要数秒甚至数十秒进行数据检索和计算。如果只是显示一个旋转的 Loading 图标，用户会感到焦虑且无法判断系统是否在有效工作。

Codex SDK 输出的 reasoning.delta 事件允许我们将 AI 的“内心独白”实时推送到前端 1。UI 设计上，可以采用一个可折叠的“思考过程”面板：

- *收到 reasoning.delta: "正在检索 BTC-USD 历史数据..."* -> UI 更新进度条。
- *收到 item.created: "调用 Yahoo Finance 工具..."* -> UI 显示工具图标闪烁。
- *收到 reasoning.delta: "计算相关系数..."* -> UI 显示计算状态。
这种设计不仅优化了等待体验，更重要的是增强了 **可解释性（Explainability）**，让用户确信 AI 是基于真实数据而非臆想进行回答。

### 7.2 背压处理（Backpressure Handling）

由于 Codex 代理生成数据的速度可能快于前端渲染或网络传输的速度，后端必须实现背压控制。Codex SDK 的 runStreamed 方法返回的是异步迭代器（Async Iterator），天然支持背压。如果前端 WebSocket 缓冲区满，后端可以暂停从迭代器读取数据，从而暂停代理的执行，直到前端消化完当前数据。这种机制有效防止了在高频数据推送下的内存溢出问题，确保了系统的稳定性 1。

## 8. 结论与展望

本报告详细阐述了基于 **OpenAI Codex SDK** 构建 **FinChat** 系统的技术路径。通过创造性地结合 **ChatGPT Pro 订阅鉴权**、**二进制封装运行时**、**MCP 数据集成** 以及 **Zod 结构化输出**，我们在极大降低运营成本的同时，构建了一个具备深度推理能力和实时数据访问权限的专业级金融代理。

该架构不仅满足了用户“利用现有 Credits 减少 API 调用”的核心诉求，更通过引入原生上下文压缩和严格的沙箱安全策略，解决了传统 RAG 系统在长文档分析上的痛点以及金融应用对数据安全的高要求。FinChat 代表了未来 AI 应用开发的一个重要方向：**从依赖云端 API 的瘦客户端模式，转向利用本地算力和订阅制推理资源的富代理（Fat Agent）模式**。这一范式转移将赋予开发者更大的自由度，去构建更复杂、更智能且更具成本效益的垂直领域应用。

#### 引用的著作

1. Codexsdk 高级用法与最佳实践
1. OpenAI Codex SDK - Promptfoo, 访问时间为 十二月 31, 2025， [https://www.promptfoo.dev/docs/providers/openai-codex-sdk/](https://www.promptfoo.dev/docs/providers/openai-codex-sdk/)
1. README — Codex SDK v0.4.2 - Hexdocs, 访问时间为 十二月 31, 2025， [https://hexdocs.pm/codex_sdk/](https://hexdocs.pm/codex_sdk/)
1. Authentication - OpenAI for developers, 访问时间为 十二月 31, 2025， [https://developers.openai.com/codex/auth](https://developers.openai.com/codex/auth)
1. Codex Install on Linux without Browser not possible? : r/ChatGPTCoding - Reddit, 访问时间为 十二月 31, 2025， [https://www.reddit.com/r/ChatGPTCoding/comments/1nphspy/codex_install_on_linux_without_browser_not/](https://www.reddit.com/r/ChatGPTCoding/comments/1nphspy/codex_install_on_linux_without_browser_not/)
1. codex/docs/authentication.md at main · openai/codex - GitHub, 访问时间为 十二月 31, 2025， [https://github.com/openai/codex/blob/main/docs/authentication.md](https://github.com/openai/codex/blob/main/docs/authentication.md)
1. Enable Headless or Command-line Authentication for Codex CLI (ChatGPT Plans) #3820, 访问时间为 十二月 31, 2025， [https://github.com/openai/codex/issues/3820](https://github.com/openai/codex/issues/3820)
1. Codex Pricing - OpenAI for developers, 访问时间为 十二月 31, 2025， [https://developers.openai.com/codex/pricing/](https://developers.openai.com/codex/pricing/)
1. Introducing the Codex IDE extension - Coding with ChatGPT, 访问时间为 十二月 31, 2025， [https://community.openai.com/t/introducing-the-codex-ide-extension/1354930](https://community.openai.com/t/introducing-the-codex-ide-extension/1354930)
1. Yahoo Finance MCP server - Apify, 访问时间为 十二月 31, 2025， [https://apify.com/nmdmnd/yahoo-finance/api/mcp](https://apify.com/nmdmnd/yahoo-finance/api/mcp)
1. A Model Context Protocol (MCP) server that lets your AI interact with Yahoo Finance to get comprehensive stock market data, news, financials, and more - GitHub, 访问时间为 十二月 31, 2025， [https://github.com/AgentX-ai/yahoo-finance-server](https://github.com/AgentX-ai/yahoo-finance-server)
1. barvhaim/yfinance-mcp-server: MCP server for Yahoo Finance (Unofficial) - GitHub, 访问时间为 十二月 31, 2025， [https://github.com/barvhaim/yfinance-mcp-server](https://github.com/barvhaim/yfinance-mcp-server)
1. Unlocking Financial AI: A Deep Dive into the Yahoo Finance MCP Server, 访问时间为 十二月 31, 2025， [https://skywork.ai/skypage/en/financial-ai-yahoo-finance/1978394270153089024](https://skywork.ai/skypage/en/financial-ai-yahoo-finance/1978394270153089024)
1. OpenAI Codex 高阶技术落地案例
1. trafflux/pdf-reader-mcp - GitHub, 访问时间为 十二月 31, 2025， [https://github.com/trafflux/pdf-reader-mcp](https://github.com/trafflux/pdf-reader-mcp)
1. labeveryday/mcp_pdf_reader: This mcp server will analyze and read pdf data. - GitHub, 访问时间为 十二月 31, 2025， [https://github.com/labeveryday/mcp_pdf_reader](https://github.com/labeveryday/mcp_pdf_reader)
