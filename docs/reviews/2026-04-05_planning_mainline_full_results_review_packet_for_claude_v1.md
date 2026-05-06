# 2026-04-05 Planning Mainline Full Results Review Packet For Claude v1

## 1. 这份文档的目的

这份文档不是新的方案文档，而是给 `Claude` 做结果评审用的总审查包。

它回答 4 个问题：

1. 用户一开始真正要的效果是什么。
2. 这条 planning 主线到底做成了什么。
3. 哪些效果已经有硬 evidence 支撑。
4. 哪些效果仍然不能诚实宣称“已经达到最终态”。

目标是让评审者不用自己在几十份 review、walkthrough、artifact 之间来回拼接。

## 2. 原始目标是什么

最初目标的权威来源是：

- [2026-04-03_planning_agent_new_session_handoff_v2.md](./2026-04-03_planning_agent_new_session_handoff_v2.md)
- [2026-04-03_planning_agent_full_unfinished_implementation_plan_v7.md](./2026-04-03_planning_agent_full_unfinished_implementation_plan_v7.md)
- [2026-04-05_planning_agent_mature_stability_gap_analysis_and_completion_plan_v1.md](./2026-04-05_planning_agent_mature_stability_gap_analysis_and_completion_plan_v1.md)
- [2026-04-05_planning_agent_mature_stability_execution_todolist_v1.md](./2026-04-05_planning_agent_mature_stability_execution_todolist_v1.md)

把这些文档里真正的用户效果抽出来，目标其实是：

1. 做成一条真实可用的 `planning` 工作主链，不是 demo。
2. 能接正式 planning 任务，而不是只会临时回答。
3. 能记住历史、上下文和当前进展。
4. 能继续同一件事，不靠聊天窗口临时记忆。
5. 结果要能直接进入工作流，不是泛泛建议。
6. 出错时不能假装完成，要 fail-close，而且 session/task truth 要一致。
7. 正常用户不应该被迫知道内部 `task_type`、provider、lane 这些实现细节。
8. 最终要走向“成熟稳定、长期可依赖”，而不是“碰巧这轮跑通了”。

## 3. 当前我主张已经做到的效果

我当前的主张不是“所有最终形态都做完了”，而是下面这句更窄、也更诚实的话：

> 在当前已建模并已证明的 planning 主线范围内，系统已经成为一条可直接拿来干正常 planning 工作的工作流：常见 planning 请求能自动进对 profile 和主路径，同一件事能继续/branch，repo-backed 实施计划能默认走 coding-agent，薄答案和缺关键段落的答案会 fail-close，而且 response / session / task truth 已经对齐。

这条主张当前冻结在：

- [2026-04-05_planning_agent_total_plan_execution_master_v64.md](./2026-04-05_planning_agent_total_plan_execution_master_v64.md)

## 4. 当前不应过度宣称的边界

下面这些我认为仍然不能硬说“已经完全做到”：

1. 还不能说“所有未来执行层都成熟稳定”。
2. 当前被真实证明的 execution lanes 仍然主要是：
   - `web`
   - `coding_agent`
3. 还不能说 `workspace` 和 `specialized` 已纳入同一套最终稳定合同。
4. 还不能把“当前 planning 主线可用”偷换成“完整统一多执行器平台已经成熟稳定”。

这条边界的最新权威口径见：

- [2026-04-05_planning_execution_layer_boundary_and_live_validation_guardrails_execution_review_v1.md](./2026-04-05_planning_execution_layer_boundary_and_live_validation_guardrails_execution_review_v1.md)
- [2026-04-05_planning_agent_total_plan_execution_master_v60.md](./2026-04-05_planning_agent_total_plan_execution_master_v60.md)
- [2026-04-05_planning_agent_total_plan_execution_master_v64.md](./2026-04-05_planning_agent_total_plan_execution_master_v64.md)

## 5. 原目标 vs 当前效果对比

| 原目标 | 当前判断 | 说明 | 关键证据 |
|---|---|---|---|
| 能接正式 planning 任务 | 已达到 | planning 已是正式 task plane，而不是零散 prompt | [W2 review](./2026-04-04_w2_planning_task_explicit_handoff_enforcement_execution_review_v1.md), [W2 review](./2026-04-04_w2_planning_task_handoff_artifact_and_evidence_bundle_execution_review_v1.md) |
| 能记住历史和当前进展 | 已达到 | `task_id / checkpoint / continue / branch / task_get / session_get` 都已成形 | [W2 review](./2026-04-04_w2_planning_task_read_semantics_explicitization_execution_review_v1.md), [continuity pack](../dev_log/artifacts/planning_phase1_continuity_acceptance_pack_20260403_v1/manifest.json) |
| 能持续推进同一件事 | 已达到 | 同 task continue、branch 新 task、不污染原 task 都有 evidence | [continuity pack](../dev_log/artifacts/planning_phase1_continuity_acceptance_pack_20260403_v1/manifest.json), [user readiness v4](../dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/manifest.json) |
| 结果能直接进入工作流 | 基本达到 | 高频 planning 场景已有固定结构和可用性 evidence | [W5 review](./2026-04-04_w5_planning_task_plane_p0_acceptance_execution_review_v1.md), [user readiness quality gate review](./2026-04-05_planning_user_readiness_and_quality_gate_execution_review_v1.md) |
| 出错不能假装完成 | 已达到 | 薄答案、缺关键段落答案、cancel / fail 路径都 fail-close | [W1 review](./2026-04-04_w1_live_triage_and_task_truth_alignment_execution_review_v1.md), [quality gate review](./2026-04-05_planning_user_readiness_and_quality_gate_execution_review_v1.md) |
| 不要求用户理解内部 task_type/provider | 基本达到 | stable planning profiles 自动主路径，自然语言和附件线索自动识别更强 | [auto main path review](./2026-04-05_planning_auto_main_path_default_execution_review_v1.md), [auto understanding review](./2026-04-05_planning_auto_understanding_from_language_and_attachments_execution_review_v1.md) |
| repo-backed 深度实施计划应进入更强执行层 | 已达到 | repo-backed `implementation_plan` 默认走 `coding_agent + codex` | [coding agent review](./2026-04-05_planning_coding_agent_execution_lane_delivery_execution_review_v1.md), [coding-agent acceptance](../dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/manifest.json) |
| 成熟稳定、长期可依赖 | 部分达到 | 当前已接近“可直接用的第一版工作系统”，但仍不应宣称所有最终形态已闭环 | [gap analysis](./2026-04-05_planning_agent_mature_stability_gap_analysis_and_completion_plan_v1.md), [master v64](./2026-04-05_planning_agent_total_plan_execution_master_v64.md) |

## 6. 用户现在实际可以怎么用

按当前冻结结果，用户实际可以期待下面的体验：

1. 直接用正常工作语言发 planning 请求，不需要先选 provider。
2. `project_diagnosis / research_decision / leadership_report / planning_general` 这类常见 planning 请求能自动进入正确 profile。
3. `请整理一版业务推进方案和下一步计划` 这类自然语言表达可以直接落到 `planning_general`。
4. `请先帮我整理一下今天材料` 这类泛化请求，如果附件元数据已表明是 `meeting_transcript`，会直接落到 `meeting_summary`。
5. repo-backed `implementation_plan` 会默认走 `coding_agent + codex`。
6. 同一件事可以 `continue`，也可以 `branch` 成新任务线。
7. 结果太薄，或者长但缺关键段落，不会伪装成完成，而会收口成 `needs_followup`。
8. 一旦 fail-close，truth 会同时体现在首答、`session_get`、`task_get`。

## 7. 主要改动按 tranche 汇总

### Tranche A: `W1` live triad 与 task truth 对齐

关键提交：

- `e6696730` `planning: align gemini task truth on completion and cancel`
- `76e2121d` `Unblock ChatGPT planning live completion gate`

关键效果：

1. `success / fail / cancel` 不再只停在 job/controller 层，开始和 session/task/checkpoint 对齐。
2. ChatGPT planning live completion gate 跑通。
3. `chatgpt_web` 的真实链路不再被误说成“还没通”。

关键文档：

- [2026-04-04_w1_live_triage_and_task_truth_alignment_execution_review_v1.md](./2026-04-04_w1_live_triage_and_task_truth_alignment_execution_review_v1.md)
- [2026-04-04_w1_chatgpt_live_lane_unblock_and_completion_execution_review_v1.md](./2026-04-04_w1_chatgpt_live_lane_unblock_and_completion_execution_review_v1.md)

### Tranche B: `W2` handoff / read semantics / artifact bundle

关键提交：

- `a5836974` `Enforce explicit planning task handoff contracts`
- `8bd3fe6c` `Make planning task read semantics explicit`
- `80e33132` `Upgrade planning task handoff artifact bundle`

关键效果：

1. 继续做同一任务不再靠模糊 session 语义。
2. `continue / branch / retrieve` 的 contract 更硬。
3. `task_get / task_list` 的 read semantics 更明确。

关键文档：

- [2026-04-04_w2_planning_task_explicit_handoff_enforcement_execution_review_v1.md](./2026-04-04_w2_planning_task_explicit_handoff_enforcement_execution_review_v1.md)
- [2026-04-04_w2_planning_task_read_semantics_explicitization_execution_review_v1.md](./2026-04-04_w2_planning_task_read_semantics_explicitization_execution_review_v1.md)
- [2026-04-04_w2_planning_task_handoff_artifact_and_evidence_bundle_execution_review_v1.md](./2026-04-04_w2_planning_task_handoff_artifact_and_evidence_bundle_execution_review_v1.md)

### Tranche C: `W3` lane policy 与 source-material action contract

关键提交：

- `8c1b8b62` `Land planning lane policy and preflight action contract`

关键效果：

1. planning task 不再只有 task truth，也开始显式暴露 lane policy。
2. source-material preflight 有了动作合同。
3. 全阻断材料 bundle 会 fail-close。

关键文档：

- [2026-04-04_w3_planning_lane_policy_and_source_material_action_contract_execution_review_v1.md](./2026-04-04_w3_planning_lane_policy_and_source_material_action_contract_execution_review_v1.md)

### Tranche D: `W4` knowledge ingress 与 memory writeback

关键提交：

- `9ec8f05d` `Land W4 planning knowledge ingress and writeback`

关键效果：

1. knowledge ingress 进入 canonical planning path。
2. memory writeback 至少进入可见、可追踪状态。

关键文档：

- [2026-04-04_w4_planning_knowledge_ingress_and_memory_writeback_execution_review_v1.md](./2026-04-04_w4_planning_knowledge_ingress_and_memory_writeback_execution_review_v1.md)

### Tranche E: `W5` P0 五场景 acceptance

关键提交：

- `18d1bcae` `Freeze W5 planning task plane P0 acceptance`

关键效果：

1. `meeting_sedimentation / workforce_planning / project_diagnosis / research_decision / leadership_report` 收成统一 acceptance pack。
2. planning 质量开始有场景化证据，而不是只有零散样例。

关键文档与 evidence：

- [2026-04-04_w5_planning_task_plane_p0_acceptance_execution_review_v1.md](./2026-04-04_w5_planning_task_plane_p0_acceptance_execution_review_v1.md)
- [planning_task_plane_p0_acceptance_pack_20260404_v1/manifest.json](../dev_log/artifacts/planning_task_plane_p0_acceptance_pack_20260404_v1/manifest.json)

### Tranche F: `W6` authority-first planning truth surface

关键提交：

- `138348a4` `Consolidate W6 planning truth query surface`

关键效果：

1. `planning_query` 开始成为 authority-first truth surface。
2. plugin 不再只靠各自私有拼装字段。

关键文档：

- [2026-04-04_w6_planning_truth_surface_consolidation_execution_review_v1.md](./2026-04-04_w6_planning_truth_surface_consolidation_execution_review_v1.md)

### Tranche G: execution-layer boundary 收紧与 coding-agent lane 接入

关键提交：

- `80946d44` `Reset planning execution-layer contract and live validation guards`
- `b5685048` `Freeze planning execution-layer boundary and live evidence`
- `c6e5451c` `Add coding-agent planning execution lane`
- `8eac35ad` `Freeze planning coding-agent lane evidence`

关键效果：

1. 不再模糊宣称“planning 已接通完整执行层”。
2. 当前 scope 被收紧成 `web + coding_agent` 的已证明执行层。
3. `coding_agent` lane 正式进入 planning 主链。
4. repo-backed 实施计划可以默认进入 `coding_agent + codex`。

关键文档与 evidence：

- [2026-04-05_planning_execution_layer_boundary_and_live_validation_guardrails_execution_review_v1.md](./2026-04-05_planning_execution_layer_boundary_and_live_validation_guardrails_execution_review_v1.md)
- [2026-04-05_planning_coding_agent_execution_lane_delivery_execution_review_v1.md](./2026-04-05_planning_coding_agent_execution_lane_delivery_execution_review_v1.md)
- [planning_coding_agent_lane_acceptance_20260405_v1/manifest.json](../dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/manifest.json)

### Tranche H: user-readiness / quality gate / auto main path / auto understanding

关键提交：

- `7a992830` `Default repo-backed planning to coding-agent lane`
- `a1f10d21` `Specialize planning scenario packs by task type`
- `c4f2b7d5` `Keep planning quality-gate truth durable`
- `dca40e42` `Tighten planning user-readiness quality gate`
- `8c85f4f9` `Default stable planning profiles to main path`
- `d06d1e7b` `Make planning auto-understand language and transcript signals`

关键效果：

1. 高频 planning profile 有固定结构要求，不再只靠长度判断。
2. stable planning profiles 自动选主路径，不再要求用户选 provider。
3. 自然语言和附件元数据驱动的自动识别更接近日常使用。
4. 形成更强的 user-readiness 证据集。

关键文档与 evidence：

- [2026-04-05_planning_user_readiness_and_quality_gate_execution_review_v1.md](./2026-04-05_planning_user_readiness_and_quality_gate_execution_review_v1.md)
- [2026-04-05_planning_auto_main_path_default_execution_review_v1.md](./2026-04-05_planning_auto_main_path_default_execution_review_v1.md)
- [2026-04-05_planning_auto_understanding_from_language_and_attachments_execution_review_v1.md](./2026-04-05_planning_auto_understanding_from_language_and_attachments_execution_review_v1.md)
- [planning_user_readiness_acceptance_pack_20260405_v4/manifest.json](../dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/manifest.json)

## 8. 关键代码面汇总

Claude 如果要抽检代码，而不是只看文档，建议先看这些文件。

### 8.1 任务真相与 northbound surface

- `/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/planning/meeting_task_store.py`
- `/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-advisor/index.ts`

### 8.2 scenario / profile / 自动理解

- `/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/scenario_packs.py`

### 8.3 execution layer / coding-agent

- `/vol1/1000/projects/ChatgptREST/chatgptrest/controller/engine.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/controller/coding_agent_executor.py`

### 8.4 knowledge ingress / runtime pack

- `/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/planning_runtime_pack_search.py`

### 8.5 evidence harnesses

- `/vol1/1000/projects/ChatgptREST/chatgptrest/eval/planning_task_plane_p0_acceptance.py`
- `/vol1/1000/projects/ChatgptREST/chatgptrest/eval/planning_user_readiness_acceptance.py`
- `/vol1/1000/projects/ChatgptREST/ops/export_planning_task_plane_p0_acceptance_pack.py`
- `/vol1/1000/projects/ChatgptREST/ops/export_planning_user_readiness_acceptance_pack.py`

## 9. 关键 evidence 汇总

下面这些 evidence 是我认为最应该被 Claude 抽查的。

### 9.1 continuity 与早期主链稳定性

- [openclawbot_planning_task_plane_acceptance_pack_20260403_v2/manifest.json](../dev_log/artifacts/openclawbot_planning_task_plane_acceptance_pack_20260403_v2/manifest.json)
- [planning_phase1_continuity_acceptance_pack_20260403_v1/manifest.json](../dev_log/artifacts/planning_phase1_continuity_acceptance_pack_20260403_v1/manifest.json)

### 9.2 live planning gates

- [openclawbot_planning_task_plane_live_completion_gate_20260404_chatgpt_v6/manifest.json](../dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_chatgpt_v6/manifest.json)
- [openclawbot_planning_task_plane_live_completion_gate_20260404_chatgpt_v6/report_v1.md](../dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260404_chatgpt_v6/report_v1.md)
- [openclawbot_planning_task_plane_live_completion_gate_20260405_gemini_auto_v2/manifest.json](../dev_log/artifacts/openclawbot_planning_task_plane_live_completion_gate_20260405_gemini_auto_v2/manifest.json)

### 9.3 P0 planning quality

- [planning_task_plane_p0_acceptance_pack_20260404_v1/manifest.json](../dev_log/artifacts/planning_task_plane_p0_acceptance_pack_20260404_v1/manifest.json)
- [planning_task_plane_p0_acceptance_pack_20260404_v1/report_v1.md](../dev_log/artifacts/planning_task_plane_p0_acceptance_pack_20260404_v1/report_v1.md)

### 9.4 coding-agent lane

- [planning_coding_agent_lane_acceptance_20260405_v1/manifest.json](../dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/manifest.json)
- [planning_coding_agent_lane_acceptance_20260405_v1/report_v1.md](../dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/report_v1.md)
- [planning_coding_agent_lane_acceptance_20260405_v1/session_snapshot_v1.json](../dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/session_snapshot_v1.json)
- [planning_coding_agent_lane_acceptance_20260405_v1/task_snapshot_v1.json](../dev_log/artifacts/planning_coding_agent_lane_acceptance_20260405_v1/task_snapshot_v1.json)

### 9.5 最终用户效果

- [planning_user_readiness_acceptance_pack_20260405_v4/manifest.json](../dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/manifest.json)
- [planning_user_readiness_acceptance_pack_20260405_v4/report_v1.md](../dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/report_v1.md)
- [planning_user_readiness_acceptance_pack_20260405_v4/meeting_summary_attachment_profile.json](../dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/meeting_summary_attachment_profile.json)
- [planning_user_readiness_acceptance_pack_20260405_v4/planning_general_profile.json](../dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/planning_general_profile.json)
- [planning_user_readiness_acceptance_pack_20260405_v4/repo_backed_implementation_defaults_to_coding_agent.json](../dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/repo_backed_implementation_defaults_to_coding_agent.json)

## 10. 我认为最值得 Claude 重点质疑的点

我不希望 Claude 只做“复述式认可”。我认为它最应该挑战下面这些点：

1. 我当前把“用户效果已经做到”界定在 `planning` 主线和当前已证明 execution lanes 范围内，这个边界是否足够诚实。
2. `planning_user_readiness_acceptance_pack_20260405_v4` 的 `10/10` 是否真的足以支持“可直接拿来用”的主张。
3. `repo-backed implementation -> coding_agent + codex` 的默认路径是否真的已经足够稳定，还是只是单 lane 证明。
4. `natural language + attachment metadata` 的自动理解是否有过度拟合样例的风险。
5. `planning_query` / `session` / `task` truth surface 是否真的已经足够让普通调用方不需要理解内部状态机。
6. 当前 evidence 是否已经足够支持“用户不需要知道内部 task_type/provider/lane”的主张。
7. 是否还有任何我在文档中低估了的剩余鸿沟，导致当前结果更像“高质量 phase-1”而不是“真的可依赖”。

## 11. 我给 Claude 的明确评审问题

建议 Claude 直接回答这 6 个问题：

1. 按原始目标，当前结果是否已经做成“一条真实可用的 planning 工作主链”？
2. 如果答案是“是，但有边界”，这个边界应该怎么表述才不夸大？
3. 当前 evidence 是否足够支持“正常 planning 用户不需要理解内部 task_type/provider/lane”这条 claim？
4. 当前 evidence 是否足够支持“结果可以直接进入工作流，而不是泛泛建议”这条 claim？
5. 现在最真实的剩余差距是什么？
6. 若只允许一句最终结论，Claude 会给：
   - `达到预期`
   - `基本达到预期`
   - `未达到预期`
   三者中的哪一个？

## 12. 我的自评

我的自评是：

> `基本达到预期，但必须带范围限定。`

原因是：

1. 这条 planning 主线已经不是 demo，而是可以直接拿来处理正常 planning 工作。
2. 当前 user-readiness evidence 已经证明：
   - 自动理解请求
   - 自动进主路径
   - repo-backed 默认进 coding-agent
   - 同 task continuity
   - fail-close
   - truth alignment
3. 但我仍然不认为可以直接把这个结果说成“完整统一多执行器平台已经成熟稳定”。

所以如果 Claude 认为我要把当前结果表述成：

> “在当前已证明的 planning 主线范围内，已经做成一条真实可用、结果可直接进入工作流的 planning 工作系统”

我认为这是合理 claim。

如果 Claude 认为我要把当前结果表述成：

> “所有最终形态都已经实现，长期稳定已经全面闭环”

那我认为这个 claim 仍然过头。

## 13. 推荐给 Claude 的阅读顺序

如果 Claude 时间有限，建议按这个顺序读：

1. 本文档
2. [2026-04-03_planning_agent_new_session_handoff_v2.md](./2026-04-03_planning_agent_new_session_handoff_v2.md)
3. [2026-04-05_planning_agent_mature_stability_gap_analysis_and_completion_plan_v1.md](./2026-04-05_planning_agent_mature_stability_gap_analysis_and_completion_plan_v1.md)
4. [2026-04-05_planning_agent_total_plan_execution_master_v64.md](./2026-04-05_planning_agent_total_plan_execution_master_v64.md)
5. [2026-04-05_planning_coding_agent_execution_lane_delivery_execution_review_v1.md](./2026-04-05_planning_coding_agent_execution_lane_delivery_execution_review_v1.md)
6. [2026-04-05_planning_user_readiness_and_quality_gate_execution_review_v1.md](./2026-04-05_planning_user_readiness_and_quality_gate_execution_review_v1.md)
7. [2026-04-05_planning_auto_main_path_default_execution_review_v1.md](./2026-04-05_planning_auto_main_path_default_execution_review_v1.md)
8. [2026-04-05_planning_auto_understanding_from_language_and_attachments_execution_review_v1.md](./2026-04-05_planning_auto_understanding_from_language_and_attachments_execution_review_v1.md)
9. [planning_user_readiness_acceptance_pack_20260405_v4/manifest.json](../dev_log/artifacts/planning_user_readiness_acceptance_pack_20260405_v4/manifest.json)

如果 Claude 还有精力，再回看：

10. [2026-04-04_w1_live_triage_and_task_truth_alignment_execution_review_v1.md](./2026-04-04_w1_live_triage_and_task_truth_alignment_execution_review_v1.md)
11. [2026-04-04_w5_planning_task_plane_p0_acceptance_execution_review_v1.md](./2026-04-04_w5_planning_task_plane_p0_acceptance_execution_review_v1.md)
12. [2026-04-04_w6_planning_truth_surface_consolidation_execution_review_v1.md](./2026-04-04_w6_planning_truth_surface_consolidation_execution_review_v1.md)
