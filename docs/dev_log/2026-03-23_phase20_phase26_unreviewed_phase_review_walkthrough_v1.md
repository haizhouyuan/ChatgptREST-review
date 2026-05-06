# Phase 20-26 Unreviewed Phase Review Walkthrough v1

## Why This Review Was Needed

此前 `Phase 20-26` 没有做过正式核验评审。当前仓里只有各阶段自己的 completion 文档，没有独立 review 文档，因此这轮的目标不是继续沿用原结论，而是：

1. 把 `Phase 20-26` 全部补做独立 review
2. 以最新 live artifact 为准，而不是只引用历史 `accepted artifact`
3. 区分“gate 假绿/假红”与“当前运行面真实漂移”

## What I Re-ran

我先重读了这 7 个 gate 的实现、runner、测试与现有 artifact：

- `chatgptrest/eval/openclaw_dynamic_replay_gate.py`
- `chatgptrest/eval/api_provider_delivery_gate.py`
- `chatgptrest/eval/auth_hardening_secret_source_gate.py`
- `chatgptrest/eval/scoped_stack_readiness_gate.py`
- `chatgptrest/eval/direct_provider_execution_gate.py`
- `chatgptrest/eval/admin_mcp_provider_compatibility_gate.py`
- `chatgptrest/eval/scoped_provider_execution_readiness_gate.py`

然后实际复跑：

- `Phase 20` runner，生成 `report_v2`
- `Phase 21` runner，生成 `report_v2`
- `Phase 22` runner，生成 `report_v5`
- `Phase 23` runner，生成 `report_v2`
- `Phase 24` runner，生成 `report_v3`
- `Phase 25` runner，生成 `report_v4`
- `Phase 26` runner，生成 `report_v2`

## What Changed Under Latest Live Evidence

`Phase 20-23` 最新复跑都仍然是绿的：

- `Phase 20`：OpenClaw 动态 replay 仍正确打到 `/v3/agent/turn`，planning 样本仍走 `clarify`
- `Phase 21`：live `/v2/advisor/advise` + same-trace EventBus 关联仍成立
- `Phase 22`：strict auth、secret source、allowlist、repo leak scan 仍成立
- `Phase 23`：聚合后仍是 `overall_passed=true`

真正的变化出现在 `Phase 24-26`：

- `Phase 24 report_v3` 不再是旧的 `GO`
  - `direct_chatgpt_low_level_blocked` 仍正确
  - `direct_gemini_submission_accepted` 仍正确
  - 但 `direct_gemini_delivery_completed` 失败，`final_status=needs_followup`
- `Phase 25 report_v4` 也不再是旧的 `GO`
  - MCP initialize 和 tools/list 仍正确
  - gemini submit 仍正确
  - 但 wait/answer 两步失败，仍然卡在 `needs_followup`
- `Phase 26 report_v2` 因为默认聚合最新上游 artifact，已经自动把 `phase24/25` 的失败带上来，因此现在是 `overall_passed=false`

## Why I Judge This As A Real Live Drift

这次我没有停在 artifact diff，而是继续直接查了两条失败 job：

- `f81be95e6629416f9f17c6c5aeda5a69`
- `87bcfbb9c8134177af13cac3bdd18371`

当前 live `/v1/jobs/{job_id}` 返回：

- `status=needs_followup`
- `recovery_status=needs_human`
- `recovery_detail` 明确提示 Gemini 当前地区不可用，需要切换 CDP Chrome 的 proxy/egress

这说明：

- `Phase 24/25` 的失败并不是“gate 读错旧 artifact”
- 也不是“只差一条更窄的断言”
- 而是当前 live Gemini provider execution path 的真实可用性已经漂了

所以 `Phase 26` 也不能继续沿用旧的 `GO`

## Final Verdict

这轮 review 后，正式口径应当更新为：

- `Phase 20 v2 = GO`
- `Phase 21 v2 = GO`
- `Phase 22 v5 = GO`
- `Phase 23 v2 = GO`
- `Phase 24 v3 = NOT GO`
- `Phase 25 v4 = NOT GO`
- `Phase 26 v2 = NOT GO`

如果后续要恢复 `Phase 24-26`，优先级不在改 gate，而在恢复 live Gemini provider execution path 的区域/代理可用性，然后重跑这三层 gate。
