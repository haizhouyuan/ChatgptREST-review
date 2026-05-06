# 2026-03-10 Codex Workstream End-to-End Summary

## 1. 起点与最初需求

这条工作线的起点不是单个 bug，而是一次系统性审计与收口任务：

- 先用 GitNexus 审核 `#83` 到 `#90` 这组系统性 issue，判断这些关于状态机、worker、executor、MCP、Advisor、KB、kernel、ops 的审计结论是否成立。
- 随后用户要求不止“评”，而是把相关系统性问题真正修掉、分支开发、分步提交、提交 PR。
- 在这之后，工作范围逐步扩大到：
  - OpenClaw 与 OpenMind v3 的深度融合架构研究
  - Cognitive substrate 后端与 OpenClaw 插件面实现
  - Gemini / ChatGPT / Qwen / maint_daemon / issue ledger / cold Codex client 等运行面修复
  - `issue_domain` canonical plane、issue graph、approval、历史回灌、runtime cutover

换句话说，这不是单轮 patch，而是一条跨“审计 -> 架构 -> 实现 -> live 修复 -> 图谱化治理”的长链路。

## 2. 第一阶段：系统性 issue 审计与收口

### 2.1 审核 `#83` 到 `#90`

最初先按 major modules 用 GitNexus + live source 复核 `#83` 到 `#90`：

- `#83` `job_store` 的状态机与 answer/result 落盘 split-brain
- `#84` `worker.py` 单体控制循环坍缩
- `#85` executors 从 provider adapter 长成 policy-heavy orchestration
- `#86` MCP server 与 driver/provider 隐藏控制面
- `#87` Advisor v3 依赖 ambient globals 与 god-router bootstrap
- `#88` KB 子系统写入与索引路径碎片化
- `#89` kernel 并行维护 `ModelRouter` 与 `RoutingFabric`
- `#90` ops 目录权力分散与重复持权

审计结论不是“几个 bug”，而是职责坍缩、权力碎片化、状态真相源不唯一、兼容路径长期不退、控制逻辑藏在隐式层里，而测试又偏 helper/happy path。

### 2.2 代码修复与 PR

这批工作最后落到了系统性修复 PR 上，过程中吸收了 reviewer 的几轮 blocker：

- 修了 `store_answer_result()` 的 lease/CAS 提交边界问题
- 修了 Advisor runtime 的 invocation-scope authority，而不是名义抽离
- 修了 Advisor runtime teardown close 残口
- 把 worker / MCP / ops 的共享控制面和修复工厂做了整合
- 最终围绕 PR `#92` / 后续 review 收口

对应代表性文档包括：

- `docs/dev_log/2026-03-07_systemic_audit_83_90_refactor.md`

## 3. 第二阶段：OpenClaw vs OpenMind v3 深度研究与架构定型

### 3.1 重新定位系统关系

经过对 OpenClaw upstream 最新 clean clone、官方文档、生态、ClawHub、showcase 与本仓库代码的双向研究，最终将关系重新定义为：

- `OpenClaw = execution shell`
- `OpenMind v3 = cognitive substrate`

这里的 `cognitive substrate` 不只是 memory，还包含：

- `memory substrate`
- `graph substrate`
- `EvoMap / evolution substrate`
- `policy / routing / long-term cognition plane`

### 3.2 核心架构判断

定下来的关键边界是：

- OpenClaw 负责：
  - session / channel / workflow / UI / approval / plugins / skills
- OpenMind 负责：
  - memory / graph / KB / long-term reasoning / evolution

不是让 OpenMind 再做一个 OpenClaw，而是让它成为 OpenClaw 的认知底座。

### 3.3 形成的 GitHub issue 与文档

这一阶段输出了两条关键 GitHub issue：

- `#96`：OpenClaw × OpenMind 深度融合与 graph / schema / pilot 的长期协同线程
- `#97`：把 OpenMind 正式定义成 cognitive substrate，OpenClaw 作为 execution shell 的顶层方案

文档落盘包括：

- `docs/reviews/2026-03-07_openclaw_openmind_deep_fusion_report.md`
- `docs/reviews/2026-03-08_openmind_cognitive_substrate_openclaw_execution_shell_plan.md`

## 4. 第三阶段：Cognitive substrate 与 OpenClaw 插件面实现

### 4.1 后端 substrate contract

按蓝图实现了认知底座后端 API 面，包括：

- `GET /v2/cognitive/health`
- `POST /v2/context/resolve`
- `POST /v2/graph/query`
- `POST /v2/knowledge/ingest`
- `POST /v2/kb/upsert`
- `POST /v2/telemetry/ingest`
- `POST /v2/policy/hints`

对应实现集中在：

- `chatgptrest/api/routes_cognitive.py`
- `chatgptrest/cognitive/context_service.py`
- `chatgptrest/cognitive/graph_service.py`
- `chatgptrest/cognitive/ingest_service.py`
- `chatgptrest/cognitive/telemetry_service.py`
- `chatgptrest/cognitive/policy_service.py`

### 4.2 OpenClaw 插件包与安装面

实现了四个 OpenClaw 插件包：

- `openclaw_extensions/openmind-advisor`
- `openclaw_extensions/openmind-memory`
- `openclaw_extensions/openmind-graph`
- `openclaw_extensions/openmind-telemetry`

并补了安装与集成面：

- `scripts/install_openclaw_cognitive_plugins.py`
- `docs/integrations/openclaw_cognitive_substrate.md`

### 4.3 产物与验证

代表性文档：

- `docs/dev_log/2026-03-08_cognitive_substrate_backend_impl.md`
- `docs/dev_log/2026-03-08_cognitive_substrate_full_impl.md`

这一阶段对应 PR：

- `#98`

## 5. 第四阶段：PR 审核、EvoMap 收口与运行时修复

### 5.1 PR #98 / PR #100 / PR #103 相关修复

在代码评审基础上，又收了多轮系统性问题：

- `PlanExecutor` 绕过 `PromotionEngine` 的 groundedness gate
- provenance 用 `INSERT OR REPLACE` 覆盖审计链
- supersession 链无环检测
- sandbox merge_back 只复制 atom 不复制关联 bundle
- 事务边界与 groundedness checker 路径问题
- worker / answer / promotion / relations / queue / ingest 等处的完整性问题

对应文档：

- `docs/dev_log/2026-03-08_merge_pr100_evomap_integrity_fixes.md`

### 5.2 Gemini / ChatGPT / Qwen / guardian / maint_daemon / issue ledger

中后段工作大量转入 live runtime：

- 修 Gemini Deep Research follow-up 链路
- 修 Gemini region / 代理 selector / Chrome 连接复用问题
- 修 Gemini plan-stub / preamble / wait/handoff 误判
- 停用并收口 Qwen 运行时与 Qwen 相关 ledger
- 修 maint daemon 的 issue automation loop
- 把 behavior-driven issue auto-promotion 跑起来
- 建立 `mitigated -> closed` 的关闭规则，并接进 guardian
- 建立 cold Codex client acceptance lane，让“新起 Codex 不知道怎么用”这类问题能被集成测试发现

代表性文档包括：

- `docs/dev_log/2026-03-08_behavior_issue_auto_promotion_loop.md`
- `docs/dev_log/2026-03-09_runtime_retro_gemini_region_and_provider_health.md`
- `docs/dev_log/2026-03-09_qwen_disable_runtime_shutdown.md`
- `docs/dev_log/2026-03-09_cold_client_codex_acceptance_lane.md`
- `docs/dev_log/2026-03-09_wait_priority_and_cold_client_quickstart.md`
- `docs/dev_log/2026-03-09_gemini_followup_thread_rebind.md`
- `docs/dev_log/2026-03-10_runtime_p0p1p2_hardening.md`

### 5.3 运行时问题治理结论

这部分最后形成了比较明确的治理机制：

- `mitigated = live 验证通过`
- `closed = mitigated 之后，至少 3 次 qualifying client success，且无复发`

open issue list / history tail / issue graph exporter 也随之建立。

## 6. 第五阶段：issue_domain canonical plane 与 issue graph

这是我后半段最集中的工作线，也是我在 `#112` 中以 `issue graph codex` 身份负责和汇报的部分。

### 6.1 先做 canonical reader 与 runtime cutover

主库已经有：

- `chatgptrest/core/issue_canonical.py`
- `chatgptrest/api/routes_issues.py`
- `tests/test_issue_canonical_api.py`

因此没有重复造 reader，而是把 `issue_domain` 从 canonical demo 推到 runtime consumer：

- 让 `/v1/issues/graph/query`
- `/v1/issues/graph/snapshot`
- `ops/export_issue_graph.py`
- `ops/export_issue_views.py`

真正以 canonical plane 为主读路径，并保留 legacy fallback。

对应提交与文档：

- `68b6225` `feat(issues): cut over issue domain reads to canonical plane`
- `ce5209c` `docs(issues): record issue domain canonical cutover`
- `docs/dev_log/2026-03-10_issue_domain_canonical_runtime_cutover.md`

### 6.2 再做 issue graph 全闭环

随后把 issue graph 补到闭环：

- verification / usage evidence 进入 canonical projection
- API / MCP / exporter / timer 打通
- live smoke issue 跑通

对应文档：

- `docs/dev_log/2026-03-09_issue_graph_closed_loop_implementation.md`

### 6.3 再做历史回灌与 approval

这一步先做真实数据审计，不是空谈：

- authoritative ledger 统计
- canonical issue plane 覆盖率
- verification / usage evidence 的历史合成情况
- family 压缩现状
- dev log / handoff history / docs 的回灌价值

先提了 `#112` 审批，请求做：

- coverage parity
- synthetic evidence provenance
- curated family registry
- stronger DocEvidence
- 暂不做 GitNexus code bridge

### 6.4 审批结论与最终落地

`#112` 最终给出的结论是：

- 这 4 项批准
- `Issue -> Commit/File/Symbol` bridge 延后一拍

随后完成并落地的提交是：

- `d99493e` `fix(issues): sync canonical issue coverage without query ceiling`
- `8172335` `feat(issues): formalize synthetic canonical evidence provenance`
- `8a70b8a` `feat(issues): add curated issue families and doc evidence`
- `b8801a7` `docs(issues): record issue-domain historical backfill phase 1`

因为本地 `master` 叠着并发改动，没有直接推脏的本地分支，而是：

1. 从 `origin/master` 拉独立干净 worktree
2. 只 cherry-pick 这 4 个已审批提交
3. 跑回归
4. 单独推送远端主线

远端最终 landed range：

- `ce5209c..089c30a`

并且在 `#112` 里完成了“审批通过 -> 主线落地”的闭环同步。

对应文档与评论：

- `docs/dev_log/2026-03-10_issue_domain_historical_backfill_phase1.md`
- `docs/reviews/2026-03-10_issue_domain_historical_data_backfill_approval.md`
- `#112` comment `4028301081`
- `#112` approval comments `4028309122`, `4028318530`
- `#112` landed comment `4028330795`

## 7. 形成的关键产物索引

### 7.1 GitHub issue / PR / 协调线程

- `#92`：系统性审计与修复收口
- `#96`：OpenClaw × OpenMind 深度融合与 graph 协调主线程
- `#97`：OpenMind cognitive substrate 顶层方案
- `#98`：cognitive substrate / OpenClaw 插件实现
- `#101`：双 web 模型评审链不可靠问题
- `#107`：Gemini UI / composer capture 治理问题
- `#109`：结构化错误指纹 ledger proposal
- `#112`：issue_domain canonical / issue graph / historical backfill 审批与同步线程

### 7.2 重要文档

- `docs/reviews/2026-03-07_openclaw_openmind_deep_fusion_report.md`
- `docs/reviews/2026-03-08_openmind_cognitive_substrate_openclaw_execution_shell_plan.md`
- `docs/reviews/2026-03-09_issue_knowledge_graph_and_retrieval_architecture.md`
- `docs/dev_log/2026-03-08_cognitive_substrate_backend_impl.md`
- `docs/dev_log/2026-03-08_cognitive_substrate_full_impl.md`
- `docs/dev_log/2026-03-09_runtime_retro_gemini_region_and_provider_health.md`
- `docs/dev_log/2026-03-09_cold_client_codex_acceptance_lane.md`
- `docs/dev_log/2026-03-09_issue_graph_closed_loop_implementation.md`
- `docs/dev_log/2026-03-10_issue_domain_canonical_runtime_cutover.md`
- `docs/dev_log/2026-03-10_issue_domain_historical_backfill_phase1.md`

### 7.3 关键代码面

- `chatgptrest/api/routes_cognitive.py`
- `chatgptrest/api/routes_issues.py`
- `chatgptrest/core/issue_canonical.py`
- `chatgptrest/core/issue_graph.py`
- `chatgptrest/core/issue_family_registry.py`
- `ops/export_issue_graph.py`
- `ops/export_issue_views.py`
- `ops/codex_cold_client_smoke.py`
- `ops/openclaw_guardian_run.py`

## 8. 当前状态

### 8.1 已经真正落地的

- `issue_domain` narrowed historical-backfill phase 已审批并 landed 到远端主线
- issue_domain canonical 读平面、verification / usage evidence、family registry、DocEvidence 已在主线
- OpenClaw / OpenMind 的深度融合方向已经不是抽象概念，而是有 API、插件、文档、审计、issue 线程协同的实物
- Gemini follow-up / wait / region / Deep Research 这条核心 runtime 线已被多轮 live 修复和验证
- cold Codex client 集成测试链已可用，能验证“新起 Codex 是否会正确使用 ChatgptREST”

### 8.2 还没有做的

- `Issue -> Commit/File/Symbol` GitNexus bridge，已明确延后
- issue-domain 之外的更大 canonical plane 统一收敛，仍在 `#96` 主线程推进
- planning / research / Codex history 与 issue domain 的跨域统一图谱，仍处于更大 graph 体系的后续阶段，不属于本轮已批准范围

### 8.3 当前工作树状态说明

写这份总结时，本地 `/vol1/1000/projects/ChatgptREST` 不是干净树：

- `master` 同时叠着其他并发 lane 的提交
- 工作树里也有用户/其他 lane 的无关改动与生成产物

因此本轮 issue-domain 的真正落地主线，是通过干净 worktree 单独完成的，不是直接从当前脏的本地 `master` 强推。

## 9. 总结

这条工作线最终完成的不是单点修 bug，而是四件事：

1. 把一组系统性审计（`#83-#90`）真正推进到代码修复与 PR 收口  
2. 把 OpenClaw × OpenMind 的关系从“模糊接入”提升为清晰的 `execution shell + cognitive substrate` 分层  
3. 把大量 runtime 问题从表层修补推进到 live 验证、issue ledger、guardian、自愈、client acceptance 的闭环  
4. 把 `issue_domain` 从 ledger demo 推到 canonical runtime consumer，再推进到有审批、有落地、有历史回灌的 issue graph 主线

如果只用一句话总结这条线：

> 从最初“审计一组系统性问题”，一路做到了“把问题治理、认知底座、运行时收口、issue graph 与主线协同真正落地”。  
