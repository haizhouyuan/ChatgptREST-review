# Review: 2026-03-16 三仓库全面审计

## 审核对象

- 原文档：
  `/vol1/1000/projects/finagent/docs/research/2026-03-16_comprehensive_three_repo_audit.md`
- 审核时间：
  `2026-03-16`
- 审核范围：
  主要校验文档中关于 `finagent × ChatgptREST × OpenClaw` 的系统级结论，尤其是自动化、调度、集成状态、测试缺口与工程债判断。

## 总结结论

这份审计 **有价值，但混淆了两个层级**：

1. `finagent` 单仓内部还缺什么
2. `finagent + ChatgptREST + OpenClaw` 作为一个系统现在已经跑到了哪一步

因此，文档里不少“单仓工程缺口”判断是成立的，但部分“系统级缺口”判断已经落后于当前 live 状态，导致整体结论偏旧、偏保守。

## 认可的判断

### 1. A/港股与估值数据能力不足

这条判断成立。当前 `finagent` 在事件、公告、source policy、sector grammar 上已经比较强，但在：

- A 股行情/成交量/估值倍数
- 港股公告与行情
- 卖方研报
- earnings call / 估值快照

这些会直接影响表达选择、赔率判断、slot justification 的数据层，还明显不足。

### 2. `theme_report.py` 的 P0 纪律层测试仍有缺口

这条判断成立。当前代码里已经有：

- `time_stop_policy`
- `diligence_budget`
- `slot_justification`

但文档中点名的 4 个新增测试函数，目前并未在 `tests/test_theme_report.py` 中看到落地同名覆盖。这个问题应保留。

### 3. `event_extraction.py` 的凭证路径硬编码问题是真实工程债

这条判断成立。当前 fallback 仍硬编码了：

- `/home/yuanhaizhou/.config/chatgptrest/chatgptrest.env`
- `/vol1/maint/MAIN/secrets/credentials.env`

这在单机上可用，但从工程规范和可迁移性看，应该进一步收口到显式配置或环境变量。

### 4. `finagent ↔ finbot` 数据仍未真正双向打通

这条基本成立。当前更像：

- `finbot` 调用 `finagent` 产出研究对象并消费其结果

而不是：

- 共享一个统一 research state
- `claim/citation/outcome` 回写到 `finagent` 事件/证据层

所以“已集成但未完全打通”是更准确的说法。

## 需要修正的判断

### 1. “event_extraction 管道未自动调度”作为三仓系统结论已过时

原文说：

> 事件抽取是手动触发，没有 cron/heartbeat 自动化

如果这句话只针对 `finagent` 单仓内部，它基本成立。  
但如果文档标题和定位是“三仓库全面审计”，这条就已经不准确。

当前系统级已经有：

- `ChatgptREST finbot`
- `ops/openclaw_finbot.py`
- `systemd user timers`
- `chatgptrest-finbot-daily-work.timer`
- `chatgptrest-finbot-theme-batch.timer`

并且已有 live rollout 文档证明 timer 已安装、已执行、结果已入 inbox。

因此更准确的写法应为：

> `finagent` 单仓没有内建 scheduler；系统级自动调度已由 `ChatgptREST finbot + systemd timers` 承担。

### 2. “OpenClaw 集成基本为零”不成立于当前系统态

原文说：

> OpenClaw 集成基本为零

这对 `finagent` 仓内本身是部分成立的，因为 `finagent` 没有直接内嵌 OpenClaw runtime。  
但对“三仓系统”不成立，因为当前已经存在：

- `main / maintagent / finbot` 的 agent 拓扑
- `main -> finbot` 委派语义
- `finbot` 交互 agent 身份
- `finbot` 的持续运行与 dashboard 产物

因此这条应改成：

> `finagent` 仓内未内嵌 OpenClaw；系统级已通过 `ChatgptREST finbot` 接入 OpenClaw 运行面。

### 3. “优秀的已知标的跟踪系统，但不是机会发现系统”说得太满

这条结论偏保守。更准确的状态是：

- discovery 能力已经存在
- 但还偏主题内、偏已知 thesis 外延
- 跨市场、跨行业、自动筛选与估值数据层不够强

因此建议改写为：

> 当前系统已经具备机会发现能力，但发现能力仍不够系统化；它更像“有 discovery 的研究 OS”，而不是“纯已知标的跟踪器”。

## 我建议的文档定位修正

如果保留这份文档主体结构，我建议把它重新定位为：

### 更准确的标题候选

- `finagent 单仓工程缺口审计`
- `三仓系统能力与 finagent 单仓缺口分离审计`

### 更准确的叙述方式

把每个判断都分两层写：

- `repo-level`
- `system-level`

这样能避免把“仓库里没做”和“系统里没跑”混成一个结论。

## 优先级建议

### P0

- 补 `theme_report` 的纪律层测试
- 收口 `event_extraction` 的凭证加载路径
- 为 A/港股/估值数据补最小可用 adapter

### P1

- 卖方研报 source role
- 估值快照写入 expression/report
- `finagent ↔ finbot` 的统一 state 设计

### P2

- 更系统化的跨市场筛选
- 更多 sector grammar
- 更强的 source / valuation / capital-market data plane

## 一句话结论

这份审计 **抓到了真实工程债，但把“仓库内缺口”写成了“系统级缺口”**。  
如果把 repo-level 和 system-level 分开，它会是一份更可信、也更适合指导下一阶段工作的审计文档。
