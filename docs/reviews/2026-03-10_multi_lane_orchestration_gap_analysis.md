# Gap Analysis: 从"人工盯 3 个 Codex"到"1 个 main agent 统一入口"

## 你现在的痛点

```
你（人类）────┬──→ KB Codex（推进 graph pilot / promotion eligibility）
              ├──→ Issue Graph Codex（推进 issue-domain canonical）
              └──→ 主库 Codex（独立审计、challenge、approve）

你在做什么：
  1. 切窗口读每个 Codex 的输出
  2. 判断 lane 间是否有矛盾
  3. 在关键节点做 approve / redirect
  4. 把跨 lane 的共识手动同步
  5. 一直盯着，不敢离开
```

## 目标状态

```
你 ───→ main agent（统一入口）
           │
           ├── 感知：汇聚所有 lane 进展
           ├── 判断：检测跨 lane 矛盾 / drift
           ├── 编排：分派任务给 sub-lane
           ├── 门控：只在关键 checkpoint 找你
           └── 记忆：历次决策 + 上下文自动传递

你只需要：
  - 看 main agent 的汇总
  - 在 checkpoint 做 approve / redirect
  - 偶尔介入 main agent 拿不准的决策
```

---

## 已经有什么（逐层清点）

### Layer 1: Agent-to-Agent 通信 — ✅ 基础已有

| 组件 | 文件 | 行数 | 状态 |
|------|------|------|------|
| `OpenClawAdapter` | `chatgptrest/integrations/openclaw_adapter.py` | 93 | ✅ `sessions_spawn/send/status` 已 wired + tested |
| `McpHttpClient` | `chatgptrest/integrations/mcp_http_client.py` | — | ✅ HTTP MCP 传输层 |
| OpenClaw topology | `scripts/rebuild_openclaw_openmind_stack.py` | ~300 | ✅ `main`(send/list/history), `maintagent`(send/list) |
| Test coverage | `tests/test_openclaw_adapter.py` | — | ✅ spawn→send→status 协议测试 |

**实际能力**：main agent 现在就可以通过 `sessions_send` 向 maintagent 等 lane 发消息，通过 `session_status` 查询状态。**协议层不是短板。**

### Layer 2: Task 分派与执行 — ✅ 单 agent 有，⚠️ 跨 lane 编排没有

| 组件 | 文件 | 行数 | 状态 |
|------|------|------|------|
| `CcNativeExecutor` | `chatgptrest/kernel/cc_native.py` | 618 | ✅ ReAct loop + MCP 工具 |
| `dispatch_headless()` | 同上 | — | ✅ 单任务发给单 agent |
| `dispatch_team()` | 同上 | — | ⚠️ 接受 TeamSpec，但只执行单个 agent，不是真多 agent 协同 |
| `dispatch_parallel()` | 同上 | — | ⚠️ 并行派任务，但各任务独立，无跨任务协调 |
| `dispatch_conversation()` | 同上 | — | ✅ 多轮对话 |
| `AgentDispatcher` | `chatgptrest/advisor/dispatch.py` | 248 | ⚠️ funnel→ContextPackage→hcom 的脚手架生成，**不是 lane 编排** |

**关键差距**：`dispatch_team` 只是"给同一个 agent 塞一个 team spec"，不是"把任务分给不同 lane 的不同 agent 然后等他们各自完成再汇总"。

### Layer 3: 进展汇聚 — ⚠️ 事件有，汇聚逻辑没有

| 组件 | 文件 | 行数 | 状态 |
|------|------|------|------|
| `EventBus` | `chatgptrest/kernel/event_bus.py` | — | ✅ TraceEvent emit/subscribe 已实现 |
| 事件类型 | cc_native.py 内部 | — | ✅ `dispatch.task_started/completed/failed`, `team.run.created/completed`, `tool.call_completed` |
| `MemoryManager` | `chatgptrest/kernel/memory_manager.py` | — | ✅ episodic stage_and_promote 已实现 |
| `EvoMapObserver` | `chatgptrest/evomap/signals.py` | — | ✅ Signal record 已实现 |

**关键差距**：
- 事件只在**单个进程内**流动（EventBus 是 in-memory）
- 没有**跨 lane 事件聚合**——KB Codex 完成了一个 milestone，main agent 无法自动知道
- 没有**进展摘要生成器**——把 N 个 lane 的 events 聚合成 1 段文字发给你

### Layer 4: 冲突检测 & 门控 — ❌ 几乎不存在

| 能力 | 现状 |
|------|------|
| 跨 lane output 矛盾检测 | ❌ 无 |
| Checkpoint 定义 | ❌ 无（你手动判断"谁到了需要我 approve 的阶段"） |
| Gate 逻辑 | ⚠️ `ApprovalQueue`（329L）存在但用于 EvoMap promotion，不用于 lane 编排 |
| Deferred line 管理 | ❌ 无（当前是 issue comment 里人工声明"不做什么"） |

### Layer 5: 统一仪表盘 / 汇总输出 — ⚠️ ops 脚本有，统一视图没有

| 组件 | 文件 | 行数 | 状态 |
|------|------|------|------|
| `openclaw_guardian_run.py` | `ops/` | 35509 | ⚠️ 巡查 + incident，但是是巡查系统健康，不是巡查 lane 进展 |
| `openclaw_orch_agent.py` | `ops/` | 24305 | ⚠️ agent 对齐 + 健康检查，但面向运维，不面向"汇总 3 个 Codex 的进展" |
| GitHub Issue comment | 外部 | — | ⚠️ 当前 3 个 Codex 的"汇聚点"是 issue comment，你手动去读 |

---

## 精确差距清单

### Gap 1: **Lane Registry — 不知道有几个 lane 在跑**

```
缺失: LaneRegistry
  - 描述: 注册/注销 active lanes 的 central registry
  - 需要: lane_id, lane_purpose, lane_agent, lane_status, last_heartbeat
  - 已有基础: openclaw_orch_agent.py 有 agent 清单概念，但与 lane 不是一回事
  - 影响: main agent 不知道有几个 lane 在跑，不知道 lane 的 purpose 是什么
```

### Gap 2: **Lane Progress Collector — 不知道每个 lane 推到哪了**

```
缺失: LaneProgressCollector
  - 描述: 定期拉取每个 lane 的进展（git log / issue comment / session_status）
  - 需要: poll 每个 lane 的最新输出，生成 structured progress delta
  - 已有基础: session_status 可以查 OpenClaw session 状态；gh API 可以读 issue comments
  - 影响: main agent 无法主动得知某 lane 有了新产出
```

### Gap 3: **Cross-Lane Coherence Checker — 不知道 lane 之间是否矛盾**

```
缺失: CoherenceChecker
  - 描述: 比较 2+ lane 的最新 output，检测矛盾或重复
  - 需要: semantic comparison（不需要完美，关键是标记 conflict points）
  - 已有基础: KB recall 可以提供 context，但没有 diff/comparison 逻辑
  - 影响: 你现在用脑子做这件事（"KB Codex 说的和主库 Codex 审出来的是否矛盾"）
```

### Gap 4: **Checkpoint / Gate Definition — 不知道什么时候该找你**

```
缺失: GateDefinition + GateEvaluator
  - 描述: 预定义哪些事件需要人类 approve
  - 需要: gate_type（e.g., "any_lane_wants_to_merge", "scope_change", "deferred_line_breach"），gate_condition
  - 已有基础: ApprovalQueue 有 review/approve 语义，但绑在 EvoMap promotion 上
  - 影响: 你只能一直盯着，因为不知道什么时候会冒出需要你决策的事情
```

### Gap 5: **Progress Digest Generator — 不能给你一句话总结**

```
缺失: DigestGenerator
  - 描述: 把 N 个 lane 的 progress deltas 聚合成 1 段人类可读的摘要
  - 需要: template-based 或 LLM-based 摘要生成
  - 已有基础: CcNativeExecutor 的 LLM 连接可以复用
  - 影响: 你必须手动读每个 lane 的 raw 输出去理解全局状态
```

### Gap 6: **Persistent Lane State — 重启后还要从头来**

```
缺失: 持久化的 lane state
  - 描述: 每个 lane 的进展状态、checkpoint 历史、决策记录
  - 需要: 写入 DB（可以复用 jobdb.sqlite3 或 memory.db）
  - 已有基础: MemoryManager 的 episodic layer 概念可以扩展
  - 影响: 如果 main agent 重启，lane 的上下文全部丢失
```

### Gap 7: **Unified Human Interface — 你的入口还是分散的**

```
缺失: 统一的人类通知通道
  - 描述: main agent 的 progress digest → 推送给你的统一通道
  - 需要: 飞书消息 / GitHub Issue comment / CLI dashboard
  - 已有基础: feishu_handler.py 存在但未完全集成；GitHub Issue comment 是当前的 de facto 汇聚点
  - 影响: 你需要在多个窗口之间切换
```

---

## 从"已有"到"目标"的最短路径

```
距离评估:
  Layer 1 (通信) ─────── 95% done ▓▓▓▓▓▓▓▓▓░
  Layer 2 (单任务执行) ── 80% done ▓▓▓▓▓▓▓▓░░
  Layer 3 (事件/记忆) ── 60% done ▓▓▓▓▓▓░░░░
  Layer 4 (编排/门控) ── 10% done ▓░░░░░░░░░
  Layer 5 (统一仪表盘) ─  5% done ░░░░░░░░░░

总体: 已有 ~50% 的底层组件，缺 ~70% 的编排/协调/汇聚逻辑
```

## 建议的实现优先级

### Phase 0: Quick Win（几个小时）
> 不建新架构，用现有工具组合一个"穷人版编排"

1. **写一个 `lane_digest.py` 脚本**：
   - 定时 `gh api` 拉 #112 / #110 / #96 的最新 comments
   - diff vs 上次拉取
   - 输出 1 段文字："哪个 lane 有新进展，新进展是什么"
   - 推送到你的终端 / 飞书

2. **给每个 Codex lane 约定一个报告格式**：
   ```
   ## Lane Status: [kb / issue_graph / main_repo]
   Progress: [what was done]
   Blocked: [yes/no, if yes what]
   Needs Approval: [yes/no, if yes what]
   ```
   这样 `lane_digest.py` 可以解析结构化输出

### Phase 1: Lane Registry + Gate（1-2 天）
1. `LaneRegistry`：一张 SQLite 表，注册 active lanes
2. `GateDefinition`：一个 YAML 配置，定义什么事件触发 checkpoint
3. 复用 `ApprovalQueue` 的 approve/reject 语义，从 EvoMap 泛化到 lane 编排
4. main agent 的 heartbeat 中加入 lane 巡检（复用 guardian 的巡检模式）

### Phase 2: Progress Collector + Digest（2-3 天）
1. `LaneProgressCollector`：通过 `session_status` + `gh api` + reader 拉取各 lane 输出
2. `DigestGenerator`：用 LLM 生成摘要（复用 `CcNativeExecutor` 的 Anthropic 连接）
3. 推送通道：先用 GitHub Issue comment（当前已有的汇聚点），后续切飞书

### Phase 3: Cross-Lane Coherence（3-5 天）
1. 两个 lane 的最新 output 做 semantic diff
2. 标记 conflict points
3. 自动在 main agent 的 digest 中标出矛盾

---

## 一句话结论

**基础设施已经走了一半**（通信、执行、事件、记忆都有），但**编排层几乎是空白**。你现在用自己的大脑充当编排层——Lane Registry + Gate + Digest 是让 main agent 替代你大脑的三个核心组件。最快的路不是从头建架构，而是先用一个 `lane_digest.py` 脚本 + 约定报告格式做 Phase 0 验证，然后再逐步把编排逻辑固化到 main agent 里。
