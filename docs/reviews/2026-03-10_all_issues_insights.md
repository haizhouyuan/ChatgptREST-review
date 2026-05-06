# GitHub Issues 全景洞察 — 2026-03-10

## 概况

| 指标 | 数值 |
|------|------|
| 总 issues | ~77 (#14–#112) |
| Open | 15 |
| Closed | 63 |
| Close rate | ~82% |
| 创建时间跨度 | 2026-03-02 — 2026-03-10 (8 天) |
| 每日创建速率 | ~9.6 issues/day |

## 洞察一：Issue 是用来思考的，不是用来管理的

**观察**：77 个 issue 在 8 天内创建，平均 ~10 issues/day。大量 issue 在创建当天或隔天就被关闭。这不是传统的项目管理（分配 → 实现 → 验证 → 关），而是**"用 issue 做外部化思维"**。

**证据**：
- #63 和 #64 是同一个 `worker.py` 拆分 issue 的重复
- #35 和 #56 是同一个"上线前待完成"清单的演化版
- #84–#90 是一次性批量发出的 7 条审计 issue，显然是一次审计 session 的产物
- #79–#82 是 Agent Teams 的 4 条有序分解 issue

**洞察**：这种用法本身不是坏事——外部化思维提高了可追溯性。但当积压的 open issues 涵盖多种粒度（从 P0 bug 到架构愿景），**没有 priority / milestone 标注**，信号就会淹没在噪声中。

**建议**：给 open issues 标 milestone 或 priority label，至少区分"本周必须"和"未来某天"。

---

## 洞察二：存在"audit issue 洪流"但几乎全部关闭，说明审计→修复闭环是健康的

**观察**：#83–#90 是一次集中审计产出的 8 条 issue，覆盖：
- #83 job_store split-brain (**唯一仍 open**)
- #84 worker.py 不可维护的单体循环 (closed)
- #85 executors 演变成 policy-heavy orchestrators (closed)
- #86 MCP server 变成隐藏控制面 (closed)
- #87 Advisor v3 依赖 ambient globals (closed)
- #88 KB 写入路径碎片化 (closed)
- #89 ModelRouter/RoutingFabric 并行维护 (closed)
- #90 ops 目录分散且重复持权 (closed)

**洞察**：7/8 关闭 = 审计发现的问题大部分被修复。唯一仍 open 的 #83（job_store split-brain）是**最深层的设计问题**——DB 状态机与文件系统产物一致性。这说明团队能处理"技术债清理"但在**事务性一致性设计**上还差一步。

---

## 洞察三：Review / 评审 issues 正在成为主要的协作载体

**观察**：当前 15 个 open issues 中有 **5 个是 review 类型**：
- #112 (KB/Graph/EvoMap state review, **28 comments** — 最活跃)
- #111 (三层评审的对外副本)
- #110 (三层评审的迭代讨论版, 持续活跃)
- #105 (post-merge review: PR #98 + #100)
- #104 (同上的重复)

**洞察**：Review-driven development 是好的模式，但 review issues 和 action issues 混在一起。#112 有 28 条 comment，这已经是一个**完整的技术讨论帖子**，不是一个需要关闭的"任务"。

**建议**：
- 区分 `type:review`（讨论型，不需要关闭）和 `type:action`（任务型，需要关闭）
- #111 和 #110 是重复的，应该关掉一个
- #104 和 #105 也是重复的

---

## 洞察四：EvoMap 三连 (#93, #94, #95) 反映了一个功能愿景在等待基础设施

**观察**：
- #93 EvoMap post-refine governance (P1/P2)
- #94 EvoMap P2 groundedness verification
- #95 EvoMap ingest agent activity closeout events

三条都是 open 状态，且在之前的 GitNexus 分析中 Evolution Plane 被验证为"0 条生产执行链"。

**洞察**：这三条 issue 描述了一个**完整的 EvoMap 闭环需求**（观察 → 验证 → 治理 → 晋级），但实际代码状态是这个闭环的管线根本没接通。这不是 issue 数量的问题，而是**开出来的 issue 在等一个还不存在的基础设施**。

**建议**：在 Memory Plane 的 vertical slice 验证完毕（#110 讨论中已确认为下一步）之前，这三条 EvoMap issue 应该标记为 `blocked-by:memory-plane-vertical-slice` 或明确降级为 M2。

---

## 洞察五：#108（MCP 后台等待不可用）是一个正在影响实际生产力的真实阻塞

**观察**：#108 描述的是 `chatgptrest_job_wait_background_start` 在默认 stateless MCP 模式下完全不可用。这直接影响了多轮外部评审循环——Codex 无法后台等待 ChatGPT Pro 长任务完成。

**洞察**：这不是一个理论问题。在这次对话中，我们用 `gh issue comment ... && sleep 30 poll` 的方式绕过了这个限制。**每一次需要等待外部模型的长任务时，都在浪费 agent 的 attention budget**。

**建议**：这可能是 15 个 open issues 中 **ROI 最高的一个**。修复方案很清楚：把 watch state 从 MCP 进程内存移到 DB-backed persistence。影响范围有限，收益直接。

---

## 洞察六：#109（错误指纹账本）代表了一条从 "救火" 到 "预防" 的演化路线

**观察**：#109 提出了结构化错误指纹流的需求——把重复出现的运行时失败（SSH 隧道抖动、OAuth 回调超时、MCP 握手回归）从"事后翻日志"变成"实时聚合 + 自动建议恢复"。

**洞察**：这是整个 issue 列表中最有**长期杠杆效应**的 issue。如果实现：
- EvoMap 就有了真正的失败信号源（当前 telemetry → promotion 断裂的核心原因之一是没有结构化的失败信号）
- Policy hints 就有了路由依据（当前 PolicyHintsService 返回 hints 但不影响任何路由决策）
- Issue ledger（已有 `routes_issues.py`）就有了自动 report 能力

**解构**：#109 不是一个独立功能，它是**连接 #83 ← #93 ← #94 ← #95 ← Policy Plane 的桥梁**。

---

## 洞察七：#83（split-brain）和 #78（agent teams design）是两个不同层面的远期项

**#83 analysis**：job_store 的 split-brain 是最老的 open issue（8 天），也是审计批次中唯一没关掉的。它需要的是 journal-first 或 2PC 语义的引入——工程量大但方向清晰。

**#78 analysis**：Agent Teams 设计是 **OpenClaw 生态扩展的产品方向**。4 个子 issue (#79–#82) 全部 closed，说明基础 data contract 和 event integration 已实现。但 #78 本身仍 open，因为 CcNativeExecutor + EvoMap 的学习循环还没有做。

**洞察**：这两个 issue 代表了两条完全不同的演进路线：
- #83 → 基础设施可靠性（向下挖）
- #78 → 产品能力扩展（向上长）

他们不应该同时推进。**基础设施先于产品扩展**。

---

## 洞察八：重复 issue 模式暴露了流程缺口

**重复项**：
- #63 和 #64 — `worker.py` 拆分（完全重复）
- #35 和 #56 — 上线前待完成清单（迭代重复）
- #104 和 #105 — post-merge review（完全重复）
- #110 和 #111 — 三层评审（意图重复，#111 是对外副本）

**洞察**：这说明创建 issue 时没有先搜索已有 issue 的习惯。对于 AI agent 创建的 issue 这可以理解，但对于人类审查来说应该在创建前快速查 existing。

**建议**：关闭 #63, #104, #111（保留 #64, #105, #110）。

---

## 总排序：15 个 Open Issues 的优先级建议

| Priority | Issue | 理由 |
|----------|-------|------|
| **P0-NOW** | #108 MCP 后台等待 | 每次长任务都浪费 attention，ROI 最高 |
| **P1-THIS-WEEK** | #83 job_store split-brain | 唯一未关的审计项，基础设施可靠性 |
| **P1-THIS-WEEK** | #109 错误指纹账本 | 打通 EvoMap + Policy 的桥梁 |
| **P2-NEXT** | #101 dual-model bogus-complete | 评审质量的信任问题 |
| **P2-NEXT** | #107 Gemini UI reference audit | 影响 driver 准确性 |
| **P2-NEXT** | #96 deep fusion arch | 大方向设计，不紧急 |
| **P3-BACKLOG** | #93, #94, #95 EvoMap 三连 | blocked by Memory Plane vertical slice |
| **P3-BACKLOG** | #78 agent teams design | 产品扩展，基础设施先 |
| **CLOSE** | #111, #104 | 重复项 |
| **TRACK** | #110, #105, #112 | Review 帖子，持续讨论 |

---

## 元观察：Issue 反映出的系统演化方向

```
Phase 0 (已过): 搭建 REST 作业队列 + driver
Phase 1 (在此): 审计→修复→稳定 v1 核心
Phase 2 (进行中): Memory Plane vertical slice
Phase 3 (计划中): Graph/EvoMap/Policy 逐条接通
Phase 4 (远期): Agent Teams + 多模型协作
```

当前系统处于 **Phase 1 → Phase 2 过渡期**。最大的风险是在核心稳定之前就开始 Phase 3/4 的工作。Issue 列表中的分布验证了这个判断。
