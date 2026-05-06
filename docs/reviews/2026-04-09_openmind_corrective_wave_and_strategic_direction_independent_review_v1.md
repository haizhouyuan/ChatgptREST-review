# OpenMind Corrective Wave & Strategic Direction Independent Review v1

Date: 2026-04-09
Reviewer: Claude (GAC independent red-team)
Scope: Codex corrective wave (commits 8ab24a65..460f3d5d), latest artifacts, and Codex strategic recommendation

## 1. 总体判断

### 1.1 对 Codex 纠偏工作的判断

这轮纠偏工作是真实的、有效的。不是文档粉饰，而是实际改变了 live DB 状态和 harness 输出。

我的独立验证结论：**纠偏工作通过。当前系统确实处于"可运营 canary 生产态"。**

### 1.2 对 Codex 战略建议的判断

Codex 给出的 P0-P4 优先级排序方向正确，但有三个地方我不完全同意，后面展开。

## 2. 纠偏工作独立验证

### 2.1 提交链完整性

6 个 commit 从 `8ab24a65` 到 `460f3d5d`，共 2802 行新增，覆盖 32 个文件。每个 commit 都有对应的 runner、test、artifact。

### 2.2 关键数据变化验证

| 指标 | 纠偏前 | 纠偏后 | 判断 |
|---|---|---|---|
| packet degraded_ratio | 1.0 | 0.0 | 真实改善 |
| packet adjusted_degraded_ratio | 0.0 | 0.0 | 保持 |
| recall case_count | 3 | 8 | 扩展了 |
| recall expected_posture_match_rate | — | 1.0 | 新增指标 |
| planning_controlled active | 0 | 31 | live DB 变化 |
| critical_rollout.buckets_without_active_atoms | 有 | [] | 清零 |
| bounded_to_noncritical_only | — | true | 新增收敛标记 |
| crystal active_crystal_count | 0 | 1 | 从零到非零 |
| graduation gate decision | — | hold | 诚实 |

### 2.3 packet degraded_ratio 从 1.0 到 0.0 的验证

这是最大的数据变化。我在前一轮 review 中指出 `degraded_ratio = 1.0` 是结构性问题。

现在 health artifact 显示 `degraded_ratio = 0.0`，`degraded_cases = []`，`degraded_source_distribution = {}`。

这说明 Codex 不是通过扩大豁免来消除 degraded，而是通过 packet harness 本身的改进让 canary cohort 的 packet 不再产生 degraded source。这是正确的修复方向。

### 2.4 planning_controlled 活跃推进验证

promotion summary 显示：
- scanned: 1833
- eligible: 31
- promoted: 31
- 分布在 3 个 query：钛虎机器人关节模组合作(12)、两轮车车轮市场竞争分析(12)、绿源来访准备(7)

筛选条件严格：`min_quality=0.72`、`min_groundedness=0.6`、`max_per_query=12`、question-shape denylist、atom_type 过滤。

这不是大水漫灌式推进，而是 narrow targeted promotion。正确。

### 2.5 retrieval guard 验证

`retrieval.py` 新增的 guard 逻辑正确：`planning_controlled` 的 atom 只在 `PLANNING_EXPLICIT_PATH` surface 上可见，其他 surface 一律返回 `None`。这防止了 planning 专用材料泄漏到非 planning 检索面。

### 2.6 crystal live evidence 验证

crystal evidence artifact 显示：
- before: `user_correction_records=0, records_scanned=0, active_crystal_count=0`
- after: `user_correction_records=4, records_scanned=1, active_crystal_count=1`

但有一个重要注脚：`manual_review_note` 明确说 "the traffic is synthetic canary evidence rather than organic end-user traffic"。

这意味着 crystal 从零到非零是真的，但这个"非零"来自合成 canary 数据，不是真实用户流量。Codex 在 artifact 里诚实标注了这一点，这是好的。

### 2.7 graduation gate 验证

gate 输出 `decision=hold`，原因是 `watch window has not yet elapsed`。所有 gate 条件（regression_ok, fail_domains=[], unapproved_warn_domains=[]）都满足，唯一阻塞是时间窗口。这是诚实的 hold，不是假绿。

### 2.8 测试验证

纠偏波次的 focused test suites 全部通过（23/23）。

## 3. 对 Codex 战略建议的独立评估

Codex 给出了 P0-P4 排序：

- P0: 飞书入口 canary 实测
- P1: 每日 operator-side watch
- P2: canary-driven 知识治理
- P3: 借 MemPalace wake-up packet
- P4: Hermes 式 skill crystallization

### 3.1 我同意的部分

**P0 飞书入口 canary 实测 — 同意这是第一优先级。**

理由充分：
- harness 已经不是瓶颈
- 当前缺的是真实用户反馈，不是更多框架
- watch window 正在跑，最有价值的事是喂真实流量

**P2 canary-driven 知识治理 — 同意不做全量大扫除。**

"跟着真实 miss 走"比"先扫全库"的 ROI 高得多。当前 recall 已经从不可用推到可用，下一步应该是 targeted 修复。

**P4 Hermes 排后面 — 同意。**

crystal 现在只有 1 个 active，而且来自合成数据。在 live volume 足够之前做 skill crystallization 是跳步。

### 3.2 我不完全同意的部分

**不同意 1：P1 的分工模型过于理想化。**

Codex 说"你做飞书真实入口提问，我做每日 health/scorecard/watch"。这个分工在概念上对，但实操上有问题：

- Codex 不是一个持续在线的 agent，它是按任务调用的
- "每日跑 health" 需要一个 cron 或 operator 手动触发，不是 Codex 自动做的
- 真正的 daily watch 应该是：你自己跑 `ops/report_openmind_production_health.py` + `ops/report_openmind_canary_scorecard.py`，或者设一个 cron job

我的建议：不要依赖"Codex 每天帮你跑"，而是把 daily watch 自动化成 cron 或 systemd timer。Codex 的价值在于异常归因和 targeted 修复，不是日常巡检。

**不同意 2：P3 wake-up packet 的优先级可能被高估了。**

Codex 说 watch window 后最值钱的架构动作是借 MemPalace 的 wake-up packet。但当前 packet 已经 `degraded_ratio=0.0`，layer coverage 中 `l0_authority_accuracy=1.0`、`l1_open_loop_usefulness=1.0`、`l3_next_step_usefulness=1.0`。唯一偏低的是 `l2_retrieval_relevance=0.5`。

这说明 packet 的主要短板不在 wake-up 编译器本身，而在 retrieval quality。所以 watch window 后的第一优先级应该是 entity-grade recall 和 retrieval ranking，不是 packet compiler 重构。

MemPalace 的 identity/essential context 注入确实值得借，但它解决的是 `personal_graph_empty` 和 `memory_identity_missing` 这类问题——这些在当前 canary cohort 里已经被处理掉了（degraded_ratio=0.0）。只有当你扩大 cohort 到更多项目时，这些 gap 才会重新暴露。

所以我的排序是：**先做 entity recall hardening（当前 entity_rate=0.0），再做 packet identity 增强。**

**不同意 3：飞书入口 canary 的"受控"程度需要更具体。**

Codex 说"先用你自己 + 1-3 个可信同事"，但没有定义：
- 什么算 canary 成功？
- 什么算 canary 失败需要回滚？
- 多少天的飞书实测数据足够做判断？
- 飞书入口的 ask 怎么回流到 recall benchmark 和 promotion pipeline？

没有这些定义，飞书 canary 就是"试试看"，不是受控实验。

## 4. 我的独立战略判断

### 4.1 当前位置

用一句话说：**工程底座已经从"搭台子"走到了"可运营 canary"，但产品验证还是零。**

对标各条线：

| 对标线 | 当前位置 | 差距 |
|---|---|---|
| Harness engineering | pre-GA canary with hard gates | 缺 daily automation 和 graduation 时间序列 |
| Anthropic 式 harness | 有 contract + runner + artifact 全套 | 缺 live traffic soak |
| MemPalace wake-up | L0-L3 packet 已实现，canary clean | identity/personal graph 在扩大 cohort 时会重新暴露 |
| Hermes crystallization | governance safe, shadow only, 1 active crystal from synthetic data | 离 live skill formation 还很远 |
| 产品可用性 | 零真实用户反馈 | 这是当前最大的未知 |

### 4.2 我的优先级排序

```
P0  飞书入口受控 canary（带明确的成功/失败定义）
P0' daily watch 自动化（cron/timer，不依赖 Codex 手动跑）
P1  entity-grade recall hardening（当前 entity_rate=0.0 是最大的 recall 短板）
P2  canary-driven targeted 知识治理（跟着飞书 miss 走）
P3  packet identity 增强（扩大 cohort 时才需要）
P4  Hermes 式 skill crystallization（等 live crystal volume 足够）
```

### 4.3 飞书 canary 的具体建议

如果现在开始飞书入口测试，我建议定义以下 hard gate：

**进入条件（已满足）：**
- packet=pass, recall=pass, crystal=pass
- regression green
- graduation gate = hold only because of watch window

**成功条件（需要定义）：**
- 7 天内至少 20 个真实 ask
- 主观满意率 > 70%（你自己打分）
- 无 critical 错误（错误归因、错误实体、authority 违反）
- recall miss 可以被 targeted 治理修复，不需要架构改动

**失败/暂停条件：**
- 出现 authority anchor 违反（packet 给出与 `_project_context.md` 矛盾的事实）
- 出现 entity 严重错配（把 A 公司的信息归到 B 公司）
- 连续 3 个 ask 的主观满意率 < 50%

**数据回流：**
- 每个飞书 ask 的 recall 结果应该被记录
- miss 的 ask 应该进入 recall benchmark 的候选集
- 新发现的 entity gap 应该触发 targeted re-ingest

### 4.4 daily watch 自动化建议

不要等 Codex 来跑。建议：

```bash
# 每天 UTC 00:00 自动跑
0 0 * * * cd /vol1/1000/projects/ChatgptREST && \
  ./.venv/bin/python ops/report_openmind_production_health.py && \
  ./.venv/bin/python ops/report_openmind_canary_scorecard.py && \
  ./.venv/bin/python ops/report_openmind_watch_window_ledger.py
```

这样 watch window 期间每天都有 artifact，graduation gate 有时间序列证据。

## 5. 对 Codex 这轮工作的最终评价

### 5.1 工程质量

这是整个系列中工程质量最高的一轮。具体表现：

- 每个 phase 都有 code + test + runner + artifact 配套
- live DB 变化是真实的（planning_controlled 0→31）
- 没有假绿（graduation gate 诚实输出 hold）
- retrieval guard 设计正确（planning_controlled 不泄漏）
- promotion 筛选条件严格（quality/groundedness/denylist/cap）
- crystal evidence 诚实标注了合成数据来源

### 5.2 诚实度

这轮的诚实度也是最高的：

- completion summary 明确说"this is still not the same as full go-live"
- residual risk note 列出了 5 个残余风险，没有回避
- graduation gate 没有被强制改成 go_live
- crystal 没有被夸大成"live learning is working"

### 5.3 保留意见

1. **recall 的 entity_rate=0.0 没有被充分讨论。** 8 个 benchmark case 全部是 bridge recall，没有一个达到 entity-grade。这意味着系统目前只能做"间接关联检索"，不能做"精确实体检索"。这个 gap 在飞书 canary 中会很快暴露。

2. **crystal 的 live evidence 来自合成数据。** 虽然 Codex 诚实标注了，但 completion summary 里说"Crystal remains pass and now has live evidence"，这个措辞容易让人误以为是真实用户产生的 evidence。更准确的说法应该是"Crystal now has synthetic canary evidence"。

3. **promotion 的 antigravity 问题仍然没有决策。** 50,765 staged atoms 占总 staged 的 52.8%。如果这个 source 不打算在近期启用 promotion，应该从 staged ratio 计算中显式排除，否则 promotion=warn 会一直存在。

## 6. 一句话结论

Codex 这轮纠偏工作扎实，当前系统确实是"可运营 canary 生产态"。下一步应该立刻开始飞书入口受控 canary，同时把 daily watch 自动化，不要依赖 Codex 手动巡检。entity-grade recall 是飞书 canary 中最可能暴露的短板。
