# Family-Aware Groundedness And Chain Backfill Walkthrough V1

Date: 2026-04-08

## 做了什么

1. 给 groundedness checker 增加 profile-aware 权重体系
2. 把 planning bulk promotion runner 切到 shared groundedness 权重逻辑
3. 给 planning review bootstrap allowlist 显式绑定 `planning` profile
4. 给 chain builder 增加 `canonical_question` conservative backfill
5. 新增 `ops/run_evomap_chain_backfill.py`
6. 对 live DB 执行：
   - `valid_from + canonical_question` backfill
   - `build_chains(copy)` 风险评估
7. 对 planning bulk promotion 执行 dry-run，判断当前 bucket / candidate 质量

## 为什么这么做

上一轮评审的关键要求有两个：

1. groundedness 权重不能只写在计划里，必须真正落到代码和 runner
2. `valid_from / canonical_question` 先补 metadata，再谈 chain / retrieval / vector

本批次就是把这两个要求先做实。

## 实际观察到的结论

1. `valid_from` 与 `canonical_question` backfill 的收益非常高，live DB 缺口几乎被补平
2. 但 `build_chains` 一旦对全库 canonical atoms 生效，会一次性制造大规模 candidate/superseded 变化
3. 所以 chain build 必须从“全库默认动作”改成“受控 family / bucket 动作”
4. planning bulk promotion 目前虽然 runner 存在，但 top slice 仍被 `planning_aios` 一类文档主导，说明 promotion 还需要更强 guardrail

## 结果

这批改动把知识治理主链从“metadata 近半缺失”推进到了：

1. live metadata 基线已经足够继续做 retrieval / vector / feedback
2. full-scope chain build 的风险已经被结构化暴露
3. 下一批可以更有把握地做 explicit fallback、vector lane 和 feedback 回路

