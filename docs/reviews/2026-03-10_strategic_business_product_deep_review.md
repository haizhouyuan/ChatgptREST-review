# 战略目标 × 业务需求 × 产品实现 — 深层评审

Date: 2026-03-10

## 一、战略定位核验

### 战略定义（来自文档）

| 层次 | 文档声称 | 代码现实 |
|------|----------|----------|
| **OpenClaw** | 执行层 shell / runtime / sessions / tools | 上游 `v2026.3.7`，未 fork ✅ |
| **OpenMind** | 认知基底 substrate（4 层：Memory / Graph / Evolution / Policy） | 代码存在，但只有 1/4 层有生产级执行链 ❌ |
| **ChatgptREST** | 集成宿主 + REST 作业队列 | 18711 端口运行、worker/driver 在线 ✅ |

### 四层架构 GitNexus 验证

| 战略层 | 代码量 | API 端点 | GitNexus execution process | 实际状态 |
|--------|--------|----------|---------------------------|----------|
| **Memory Plane** | 675L（capture 185L + context 490L） | `/v2/memory/capture` + `/v2/context/resolve` | 1 条 `memory_capture → MemoryCaptureItemResult` | ⚠️ 部分连通 — capture 有真实闭环，recall 作为 context block 返回已测试，但 cross-session 持久化依赖 in-memory runtime |
| **Graph Plane** | ~200L（ingest 374L 含 graph 写入） | `/v2/graph/query` + `/v2/knowledge/ingest` | **0 条 execution process** | ❌ API 存在，但 repo-graph federation 没有主链调用 |
| **Evolution Plane** | PromotionEngine + observer | `/v2/telemetry/ingest` | **0 条 execution process** | ❌ observer 在、governance 框架在、但 telemetry → promotion 主链未接通 |
| **Policy Plane** | 331L（PolicyHintsService） | `/v2/policy/hints` | **0 条 execution process** | ❌ hints 返回得出但不影响任何路由决策 |

**核心发现**：文档描述的是一个 4 层认知基底，但只有 Memory Plane 有可验证的生产级闭环。其余 3 层停留在"有 API 表面但无 end-to-end 主链"的状态。

## 二、业务需求满足度分析

### 需求 1：跨 session 认知增益

**文档声称**：OpenMind 通过 capture/recall 形成跨 turn / 跨 session 的认知增益。

**代码现实**：
- ✅ `MemoryCaptureService` 实现了 capture → dedup → audit 链条（3 个 checkpoint 测试全通过）
- ✅ `ContextService.resolve()` 能返回包含 captured memory 的 `ContextBlock`
- ⚠️ cross-session 依赖 `MemoryManager` 的 in-memory 持久化（sqlite backed），但 runtime reset 后需重新加载
- ❌ **没有 semantic recall** — 当前 recall 走 category 匹配 + 关键字，不是向量相似度

**满足度**：**60%** — 最小可用闭环在，但缺乏语义 recall 意味着 recall 质量上限很低。用户说"我上次提到过审计发现应该按严重程度排列"，系统靠 category match 大概率找不回来。

### 需求 2：EvoMap 自演化知识治理

**文档声称**：observer 观察执行结果 → 识别失败模式 → 通过 governed promotion pipeline 晋级知识原子。

**代码现实**：
- ✅ `TelemetryService.ingest()` 能接收 session-scoped 执行遥测
- ✅ `PromotionEngine` 代码存在，有 unit test
- ❌ **Telemetry → PromotionEngine 没有主链连接**（GitNexus 验证：0 条 process）
- ❌ `PromotionEngine` upstream impact 只命中 `evomap/evolution/executor.py:__init__`，不在任何生产 API 调用链上

**满足度**：**20%** — 框架代码在但核心管线未接通。治理层是纸面存在。

### 需求 3：Personal Agent 业务消息能力

**文档声称**：Feishu/Dingtalk 作为真实业务消息面。

**代码现实**：
- ✅ 插件在配置中声明（`feishu`, `dingtalk`）
- ⚠️ Blueprint 明确声明 Feishu doc/wiki/chat/drive/perm/scopes 全部 disabled
- ❌ `FeishuHandler` 中 `_feishu_send_card` 等信号处理函数在 GitNexus 中为死代码
- ❌ 没有任何端到端测试验证 Feishu 消息从接收到回复的完整链路

**满足度**：**15%** — 有集成声明但实际能力被禁用。作为"真实业务面"的承诺与实现严重不符。

### 需求 4：统一运维体验

**文档声称**：`lean`/`ops` 两档部署模式，一键切换。

**代码现实**：
- ✅ 文档中明确定义了 `lean`/`ops` 的 agent topology 和 tool baseline
- ❌ **没有一键切换命令**（无 CLI、无 API、无 script）
- ❌ `/health` 快速健康检查端点未实现
- ❌ `guardian`/`maintagent`/`verifier` 三者关系无文档说明

**满足度**：**25%** — 战略设计清楚但可执行的运维工具几乎为零。

## 三、产品实现评估

### 产品矩阵

| 产品能力 | 战略文档中的定义 | 代码实现 | 测试覆盖 | 生产可用 |
|----------|-----------------|----------|---------|----------|
| Memory capture | "shell 产物进入 substrate" | `MemoryCaptureService` | 3 tests ✅ | ⚠️ MVP |
| Memory recall + context injection | "下次请求自动注入" | `ContextService.resolve()` | 2 tests ✅ | ⚠️ 仅 keyword |
| Graph federation | "GitNexus + personal graph 统一查询" | `/v2/graph/query` API | 存在 | ❌ 未接通 |
| Knowledge ingest + KB writeback | "审核后写入 KB" | `KnowledgeIngestService` | 存在 | ⚠️ quarantine 模式 |
| Telemetry → EvoMap | "执行反馈驱动演化" | `TelemetryService.ingest()` | 存在 | ❌ 管线断裂 |
| Policy hints | "telemetry 感知的策略建议" | `PolicyHintsService` | 存在 | ❌ 不影响路由 |
| Promotion pipeline | "知识原子晋级治理" | `PromotionEngine` | unit tests | ❌ 未接生产 |
| Funnel decision pipeline | "需求分析 → 方案 → 执行计划" | `build_funnel_graph()` | ✅ stubbed | ❌ stage gates 死代码 |
| Lean/ops mode switch | "一键切换部署模式" | 文档定义 | 无 | ❌ 不存在 |
| Health check | "快速系统健康检测" | `/v2/cognitive/health` | 存在 | ⚠️ 仅 cognitive |
| Feishu business messaging | "主要业务消息面" | 配置声明 | 无 e2e | ❌ 功能禁用 |
| Issue domain graph | "ledger → graph → evidence → close-loop" | `routes_issues.py` | 11 tests ✅ | ✅ 生产可用 |

### 产品完整度评分

```
已生产可用的竖切片:  1/12 (issue domain)
MVP 可用:           3/12 (memory capture, recall, KB ingest)
代码存在但未接通:    5/12 (graph, telemetry, policy, promotion, funnel)
仅文档/配置:        3/12 (mode switch, health, feishu)

综合产品完整度:     ~25%
```

## 四、战略-执行断裂点分析

### 断裂点 1："4 层基底" vs "1.5 层实现"

战略文档定义了 Memory / Graph / Evolution / Policy 四层，但 GitNexus 证实只有 Memory 层有部分连通的 execution chain。这意味着：

- **战略叙事**超前于**工程现实** 2-3 个里程碑
- 正确做法：文档应该标注"M1 当前只覆盖 Memory"，而不是暗示 4 层都是 live

### 断裂点 2：Plugin 声明 vs Plugin 有效性

Blueprint 声称 4 个 OpenMind 插件（advisor, memory, graph, telemetry）是"生产基线"。但实际上：

- `openmind-memory`: capture/recall 闭环在 → ✅ 有效
- `openmind-advisor`: API 在、但 funnel stage gates 死代码 → ⚠️ 部分有效
- `openmind-graph`: API 在、但 repo-graph federation 无主链 → ❌ 无效
- `openmind-telemetry`: ingest API 在、但不驱动任何 promotion 或 policy → ❌ 无效

### 断裂点 3：运维愿景 vs 运维现实

Blueprint 定义了成熟的 lean/ops 双模运维，但实际上：

- 没有切换命令
- 没有 `/health` 端点
- guardian 是独立脚本而非拓扑成员
- 三种运维角色的边界没有文档

## 五、独立判断与建议

### 判断 1：当前状态是"认知基底的 Day-1 MVP"，不是"4 层 substrate"

这不是批评——Day-1 MVP 有价值。但文档不应该暗示 4 层已经 live。

**建议**：在 `openclaw_cognitive_substrate.md` 顶部加 maturity indicator：
- Memory Plane: **M1 MVP** (capture + keyword recall)
- Graph Plane: **M0** (API surface only)
- Evolution Plane: **M0** (framework only)
- Policy Plane: **M0** (compute-only, no routing integration)

### 判断 2：Memory Plane 是正确的优先级

Issue #110 讨论中选择 memory recall/capture 作为下一条 vertical slice 是正确的决定，理由被本次分析进一步强化——它是唯一一个已经有 production execution chain 的战略层。

但需要补充：**当前 recall 缺乏 semantic matching**，这会严重限制 cross-session 认知增益的实际价值。keyword/category match 对稍微变化的表述就会 miss。

### 判断 3：Graph 和 EvoMap 的正确顺序是"先接通 1 条 vertical slice，再扩面"

不要试图同时补齐 3 个断裂的战略层。按 Issue #110 的三泳道 + 竖切片方法论：

1. **现在**：Memory recall/capture round-trip → 证明 substrate 骨架能跑
2. **下一步**：从 Memory 向 Graph 扩展 1 条竖切片（例如"recall 时如果 keyword match 不到，fallback 到 graph 邻域查询"）
3. **再下一步**：EvoMap promotion slice — 建立在 capture + graph 稳定的基础上

### 判断 4：Feishu 集成需要要么做到、要么正式降级

当前状态是"声称是主要业务面但功能禁用"。这比"不做"更糟，因为文档给出了错误的期望。

**建议**：如果 single-user baseline 不需要 Feishu collaboration tools，就在 blueprint 中明确标注"Feishu 仅作为通知通道，不支持交互式工作流"。

### 判断 5：`_run_once` + `get_advisor_runtime` 的拆分必须在 Graph Plane 接通之前完成

因为一旦 Graph federation 接入生产路径，它必然要经过 `get_advisor_runtime` 初始化。如果那个 550L 函数还没减重，Graph 接入会进一步增加它的 blast radius（当前已经 CRITICAL）。

拆分窗口是 **现在**，不是"接完 Graph 再说"。
