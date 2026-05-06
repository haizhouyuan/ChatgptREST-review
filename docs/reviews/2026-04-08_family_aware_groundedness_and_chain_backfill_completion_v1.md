# Family-Aware Groundedness And Chain Backfill Completion V1

Date: 2026-04-08

## 1. 范围

本批次完成的是 `KB / EvoMap` 主链里的两个基础能力：

1. `family-aware groundedness`
2. `valid_from / canonical_question` backfill runner

本批次**没有**把全库 `build_chains` 直接推到 live promotion 语义，而是先把它收在 copy 评估面。

## 2. 已完成改动

### 2.1 groundedness 权重冻结并落地

文件：

- [groundedness_checker.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/groundedness_checker.py)
- [run_planning_bulk_groundedness_promotion.py](/vol1/1000/projects/ChatgptREST/ops/run_planning_bulk_groundedness_promotion.py)
- [planning_review_plane.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_review_plane.py)

本批次落地：

1. 冻结 `standard / planning / code_procedure` 三套 groundedness 权重 profile
2. `check_atom_groundedness()` / `enforce_promotion_gate()` 能根据 `scope_project / doc_source / atom_type` 推断 profile
3. planning reviewed bootstrap allowlist 明确使用 `planning` profile
4. planning bulk promotion runner 统一复用 profile-aware weighted scoring

### 2.2 metadata backfill runner 落地

文件：

- [chain_builder.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/chain_builder.py)
- [run_evomap_chain_backfill.py](/vol1/1000/projects/ChatgptREST/ops/run_evomap_chain_backfill.py)

本批次落地：

1. `derive_canonical_question()` 支持：
   - specific question
   - activity question pattern
   - generic heading skip
   - synthetic placeholder skip
2. `run_p1_migration()` 现在是：
   - `valid_from` backfill
   - `canonical_question` backfill
   - `build_chains`
3. 新增 `ops/run_evomap_chain_backfill.py`
   - dry-run 默认对 DB copy 执行
   - 支持 `--live`
   - `build-chains-mode` 支持 `skip / copy / live`

## 3. 测试结果

通过的 focused suites：

1. `tests/test_groundedness.py`
2. `tests/test_evomap_chain.py`
3. `tests/test_run_evomap_chain_backfill.py`
4. `tests/test_planning_review_plane.py`
5. `tests/test_run_planning_bulk_groundedness_promotion.py`
6. `tests/test_promotion_engine.py`
7. `tests/test_evomap_activation_pack.py`

## 4. Live 证据

### 4.1 chain backfill dry-run

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_chain_backfill/20260408T113015Z/summary.json)
- [README.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_chain_backfill/20260408T113015Z/README.md)

关键结果：

1. `valid_from_missing`: `51429 -> 199`
2. `canonical_missing`: `47829 -> 1084`
3. `build_chains(copy)` 会把 `103225` 条 atoms 收进 chain
4. dry-run 证明：
   - metadata backfill 收益高
   - 全库直接 chain build 风险过大，不适合直接 live apply

### 4.2 chain backfill live-safe apply

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_chain_backfill/20260408T113219Z/summary.json)
- [README.md](/vol1/1000/projects/ChatgptREST/artifacts/monitor/evomap_chain_backfill/20260408T113219Z/README.md)

关键结果：

1. live DB 已完成 `valid_from + canonical_question` backfill
2. live DB 后态：
   - `valid_from_missing = 199`
   - `canonical_missing = 1084`
   - `chain_id_nonempty = 0`
3. chain build 仍只在 copy 评估面运行，没有直接改变 live promotion 语义

### 4.3 planning bulk promotion dry-run

- [summary.json](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T113415Z/summary.json)
- [active_failures.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T113415Z/active_failures.tsv)
- [candidate_eligibility.tsv](/vol1/1000/projects/ChatgptREST/artifacts/monitor/planning_bulk_groundedness_promotion/20260408T113415Z/candidate_eligibility.tsv)

关键结果：

1. `max_atoms=1000` dry-run 下：
   - `eligible_active = 96`
   - `eligible_candidate = 255`
   - `active_failures = 96`
2. 当前 top-quality slice 被 `planning_aios / planning_misc` 主导，说明 bulk promotion 还需要更强 bucket/quality guardrail

## 5. 判断

本批次现在可以成立的判断是：

1. `family-aware groundedness` 已经真正落地，不再只是计划数字
2. `valid_from / canonical_question` 已经补到 live DB
3. `build_chains` 不能直接全库 live apply，必须收敛到 controlled scope
4. planning bulk promotion 仍然需要下一批继续收紧 bucket 与 fallback/activation 语义

## 6. 下一步

下一批主链继续做：

1. planning explicit fallback 护栏
2. provenance / layer 标记
3. EvoMap vector lane
4. answer_feedback / scorer 事件接线

