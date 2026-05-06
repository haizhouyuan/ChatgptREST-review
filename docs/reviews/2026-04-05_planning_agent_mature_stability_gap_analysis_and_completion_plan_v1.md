# 2026-04-05 Planning Agent Mature Stability Gap Analysis And Completion Plan v1

## 1. 目的

这份文档回答 3 个问题：

1. 现在离“成熟稳定”到底还差什么。
2. 哪些差距是真正阻止我们对外说“已经稳了”的硬缺口。
3. 哪些工作应该先做成当前可执行 tranche，哪些属于后续更高阶演进。

这里的“成熟稳定”不是指“能跑一次”，而是指：

> 这条 planning 主链可以被当作真实工作系统来依赖，入口清晰、状态可信、继续做得回来、质量有硬 gate、知识与材料处理不靠人工脑补、并且每次宣称稳定都有成体系 evidence 支撑。

## 2. 当前真实效果

按当前冻结事实，已经成立的是：

1. `OpenClawBot -> planning task plane -> continue/handoff` 主链已经能真实工作，不再只是 demo。
2. `Gemini` 与 canonical `ChatGPT` planning completion lane 都已有显式 live green evidence。
3. `success / fail / cancel` live triad 已有 truthful evidence，而不是假绿。
4. `task_id / checkpoint / explicit continue / branch / writeback` 已经有 phase-1 continuity sidecar。
5. `knowledge_ingress` 与窄 `memory_writeback` 已接入 canonical `agent_v3` path。
6. `P0` 五场景现在已有统一 acceptance pack。
7. `OpenClaw` plugin planning query surface 已经收成 authority-first `planning_query`。

也就是说：

> 核心工作主链已经拿到了，但还没有把“成熟稳定”的全部要求闭成一套 release-grade gate。

## 3. 与“成熟稳定”之间的差距

下面这些是剩余差距，按阻碍程度从高到低排序。

### G1. 缺少 release-grade 最终统一 gate

现在有很多局部 evidence：

1. live triad
2. `7/7` OpenClaw acceptance pack
3. `3/3` continuity acceptance pack
4. `5/5` P0 acceptance pack
5. knowledge ingress / writeback visibility
6. authority-first plugin truth surface

但这些还没有被重新绑定成一个统一 final gate。

这导致两个问题：

1. 你很难一句话回答“现在到底算不算过线”。
2. 后续很容易再次出现 master 文案先于硬 evidence 漂移的情况。

### G2. `7/7` 与 `3/3` 缺少 W4-W6 之后的重新绑定

这是当前最硬的证据缺口。

旧 evidence 仍然绿：

1. `openclawbot_planning_task_plane_acceptance_pack_20260403_v2` 是 `7/7 + branch`
2. `planning_phase1_continuity_acceptance_pack_20260403_v1` 是 `3/3`

但 `W4-W6` 做完之后，没有新的统一冻结证明：

1. 它们在当前代码上仍持续成立；
2. 它们与新加的 `5/5` P0 pack、knowledge ingress、authority-first truth surface 可以一起构成 release-grade claim。

### G3. authority-first planning truth 还没有推进到 server/query 全部读面

`W6` 把 authority-first `planning_query` 做到了 `openmind-advisor` plugin 层，但 server/query 读面仍然主要是：

1. `planning_task`
2. `planning_tasks`
3. `read_semantics`

这比之前清楚，但仍不是“所有 northbound 读面都显式告诉你 canonical field 是谁”。

成熟形态下应该做到：

1. REST task/session/list 面直接给 authority-first planning query contract；
2. CLI query scripts 也给同样的 authority-first projection；
3. plugin 只是复用，而不是自己再 synthesize 一遍。

### G4. knowledge writeback 还不是 durable handoff truth

当前 `memory_writeback` receipt 在 `session/control-plane` 上可见，这已经比没有强很多。

但它还不是 durable handoff truth：

1. checkpoint/handoff 没有完整持久化这份 writeback receipt；
2. 因此跨端 handoff 时，knowledge writeback 仍不算最强形态的 truth source；
3. 这会影响“做完之后到底写回了什么、下一个端能不能直接拿来接着做”的可信度。

### G5. lane policy 还是窄冻结，不是完整 policy engine

当前 lane policy 只冻结了一条很窄的 planning path。

成熟稳定要求下，至少应有：

1. task/profile -> provider posture 的显式矩阵；
2. 哪些 lane 是 stable、advisory、blocked、manual-selection-required；
3. policy 变更有对应 gate，不靠口头补充。

### G6. attachment/material policy 仍然偏“半治理”

当前已经有：

1. preflight snapshot
2. source-material action contract
3. `all blocked -> fail-closed`

但 mixed bundle 仍主要是 advisory。

成熟形态还需要：

1. mixed bundle 的明确优先级和阻断边界；
2. preprocess-first 是否允许继续执行的更硬规则；
3. 材料 family 覆盖范围的正式支持矩阵。

### G7. runtime pack 还没有升级成 promotion-grade 支撑层

当前 `planning_runtime_pack` 已有：

1. approved hits
2. bundle freshness/readiness metadata

但离成熟稳定还差：

1. freshness SLA
2. promotion/acceptance policy
3. stale pack 在主链里的 fail-closed 或 degrade 规则

### G8. 缺少日常稳定性运维 gate

现在有单点 evidence，但还没有完全变成 release routine：

1. 缺少统一 mature-stability scorecard
2. 缺少每次批次后的固定 rebind/export/checklist
3. 缺少能直接判定“是否允许继续对外宣称 stable”的 one-command gate

## 4. 最终形态下应成立的硬标准

成熟稳定，不是“文档说完成”，而是下面 10 条同时成立：

1. 同一 canonical planning 场景 live green 可以重复获得，且 provider scope 明确。
2. `success / fail / cancel` 都有真实 evidence，并且 session/task/checkpoint truth 一致。
3. `7/7 + branch` OpenClaw acceptance 在当前代码上重新冻结为绿。
4. `3/3` continuity acceptance 在当前代码上重新冻结为绿。
5. `5/5` P0 quality acceptance 在当前代码上重新冻结为绿。
6. northbound planning query surfaces 都显式告诉调用方：
   - authority
   - read_mode
   - canonical field
7. checkpoint/handoff 对跨端 continue 已是可信主线，不再依赖整段聊天回放。
8. knowledge ingress/writeback 不只是“出现过”，而是被纳入可核验 release gate。
9. 材料动作合同和 lane policy 至少在 phase-1 高频路径上明确、稳定、可解释。
10. 每一轮 stable claim 都能回指同一套 scorecard/manifest，而不是多份 review 人工拼接。

## 5. 全量剩余工作包

### W7. Mature Stability Release Gate

目标：

把分散 evidence 重新绑定成一个 release-grade scorecard。

需要完成：

1. 重新导出当前代码下的 `7/7 + branch` acceptance pack
2. 重新导出当前代码下的 `3/3` continuity pack
3. 绑定现有 `5/5` P0 pack
4. 绑定 live triad evidence
5. 导出统一 mature-stability manifest/report

验收：

1. 一个 manifest 即可判断 pass/fail
2. 缺任一关键 evidence 时 fail-closed
3. scorecard 绑定最初的 5 条总标准与 phase-1 硬 gate

### W8. Authority-First Planning Truth Surface Everywhere

目标：

把 `planning_query` 从 plugin-only contract 推进成 server/query canonical contract。

需要完成：

1. REST `task_get / task_list / session_get` 给出 authority-first planning query
2. CLI query scripts 给出同样 projection
3. plugin 改成尽量复用 server truth，而不是自行拼接独有 contract

验收：

1. 所有 northbound planning query 面都显式给出：
   - `authority`
   - `read_mode`
   - `canonical_field`
2. 新调用方不需要再猜 `planning_task` / `control_plane.planning_task` 谁更权威

### W9. Durable Knowledge Handoff

目标：

让 `memory_writeback` 进入 durable handoff truth，而不是只停在 session/control-plane。

需要完成：

1. writeback receipt 有 durable projection
2. cross-end handoff 能直接看见 writeback evidence
3. failure/no-op/writeback-skipped 语义也能留痕

验收：

1. durable artifact 能明确说明“写回了什么/没写回什么/为什么”
2. continue path 能直接借此解释当前 knowledge state

### W10. Policy And Material Contract Hardening

目标：

把窄 freeze 扩成最小可依赖 policy layer。

需要完成：

1. lane policy matrix
2. supported/preprocess-first/blocked material matrix
3. mixed bundle 处理规则

验收：

1. 高频 planning path 无 ambiguous decision
2. blocked/preprocess-first/stable 都有显式证据和返回语义

### W11. Runtime Pack Promotion Governance

目标：

让 runtime pack 从“半健康 recall 资产”升级成可依赖支撑层。

需要完成：

1. freshness SLA
2. promotion rule
3. stale/degraded handling

验收：

1. 主链不会静默消费 stale pack 冒充稳定事实
2. refreshed/promoted 状态有 evidence

### W12. Release Routine And Soak Discipline

目标：

把成熟稳定从一次性结论，变成可重复执行的日常运维流程。

需要完成：

1. stable-claim release checklist
2. scorecard export routine
3. 周期性 rebind/soak 策略

验收：

1. 后续任一批次都能同样复跑同一套 gate
2. 不再依赖人工回忆和口头拼接

## 6. 当前建议执行 tranche

虽然上面是全量差距，但当前最合适立即执行的 tranche 不是全部铺开，而是先做下面 3 件：

### T1. 重新绑定 `7/7`、`3/3`、`5/5`，并导出统一 mature-stability gate

原因：

这是当前离“能不能诚实说过线”最近的硬缺口。

### T2. 把 authority-first `planning_query` 推进到 REST / CLI server truth

原因：

现在 plugin 已经比 server truth 更清楚，这在长期上是反的；canonical truth 应回到 server/query layer。

### T3. 用统一 scorecard 把 knowledge ingress / memory writeback / live triad 绑进同一份 manifest

原因：

这样才能把“已经做出来的东西”变成真正的 release gate，而不是散装成就。

## 7. 当前 tranche 的验收标准

本 tranche 通过，必须同时满足：

1. 新导出的 `7/7 + branch` 仍绿。
2. 新导出的 `3/3` 仍绿。
3. `5/5` P0 pack 仍绿。
4. 有新的 mature-stability manifest/report，并能 fail-closed。
5. REST/CLI/server truth 读面出现 authority-first `planning_query`。
6. 对应自动化测试和 walkthrough 完整落盘。

## 8. 这份文档的角色

这份文档本身不是“已经完成”的宣称，而是：

1. 当前成熟稳定差距的 authoritative gap scan
2. 后续红队审稿的输入材料
3. 当前 executable tranche 的初始建议
