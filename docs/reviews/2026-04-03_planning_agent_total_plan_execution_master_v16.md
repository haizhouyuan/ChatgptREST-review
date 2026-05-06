# 2026-04-03 Planning Agent Total Plan Execution Master v16

## 1. v16 相比 v15 的关键变化

`v16` 的变化不是再扩任务类型，而是把 planning task plane 真正推进到了 `OpenClawBot` 主链 acceptance。

新增成立的事实：

1. `OpenClawBot` 主链现在已经有 `7 task types + explicit continue + task_get + branch` 的真实 acceptance evidence。
2. `_should_continue()` 不再是“单个材料重叠就继续”。
3. `/planning/task/{task_id}` 不再是 open-read。
4. OpenClaw plugin 已经自动把 runtime identity 带进 `task_get`。
5. plugin harness 并发缓存冲突也被补掉了。

## 2. 到 v16 为止的当前状态

### 2.1 已经进入主链证明的部分

当前已经被主链 evidence 证明的是：

1. `meeting_sedimentation`
2. `workforce_planning`
3. `implementation_plan`
4. `project_diagnosis`
5. `research_decision`
6. `leadership_report`
7. `planning_general`
8. `project_diagnosis -> leadership_report` branch
9. `explicit_continue`
10. `task_get`
11. `source_material capture`

### 2.2 这一轮明确收掉的风险

1. shared template / shared attachment 导致的明显误续接风险
2. `task_id` 被任意 authenticated caller 直接读回的风险
3. OpenClaw plugin 在并发 replay/export 时共享 `_npx` 缓存的 runtime 脆弱性

### 2.3 仍未关闭的下一批问题

当前还没有被这轮真正解决的是：

1. file-backed store 的 multi-process durability / locking
2. phase-1 sidecar truth 向 full task runtime 的长期迁移
3. 真实 provider round-trip 上的长跑 acceptance（当前 acceptance 仍用 mocked controller）

## 3. v16 的当前判断

到这一步，我的判断应改成：

1. planning task plane 现在不只是“代码存在”，而是已经有 `OpenClawBot` 主链 acceptance
2. 当前的主问题不再是入口链是否能通
3. 当前更像是：
   - 上层主链 contract 已经有证明
   - 下层 durability / concurrency 还要继续补

## 4. v16 的 Next 3

### 4.1 Next 1

基于这次 `v16` 代码，再跑一次 strict `claudegac`。

### 4.2 Next 2

开始处理 file-backed planning store 的 multi-process safety：

1. 是否加 file lock
2. 是否显式声明 single-process only
3. 需要哪一层 evidence 才能签

### 4.3 Next 3

准备把当前 mocked-controller acceptance 再往真实 provider/长跑 evidence 推一层，但不改变 `publicagentmcp` 的薄边界定位。

## 5. 一句话结论

`v16` 的核心变化是：

> planning task plane 已经从 repo-internal proof 升级到 `OpenClawBot` 主链 proof，同时把 `implicit continue` 和 `task lookup owner boundary` 两个直接风险收进了代码。
