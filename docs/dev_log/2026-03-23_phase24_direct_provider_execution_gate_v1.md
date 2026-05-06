# Phase 24 Direct Provider Execution Gate v1

## Goal

补一层 scoped provider execution 证据，证明两件事：

- direct low-level `/v1/jobs` 上，`chatgpt_web.ask` 仍被严格阻断
- 同一层 low-level surface 上，允许的 generic provider 路径 `gemini_web.ask` 仍能真实提交并完成交付

## Final Evidence

- accepted artifact: [report_v2.json](/vol1/1000/projects/ChatgptREST/docs/dev_log/artifacts/phase24_direct_provider_execution_gate_20260323/report_v2.json)

## Final Checks

- `direct_chatgpt_low_level_blocked`
- `direct_gemini_submission_accepted`
- `direct_gemini_delivery_completed`

## Notes

- `report_v1` 不是当前真值。首轮失败是 gate 自己的认证与策略取样错误：
  - 误复用了 public ingress 的 `OPENMIND_API_KEY` 逻辑，导致 `/v1/jobs` 返回 `401`
  - Gemini 提交用了 `preset=pro + 过短问题`，撞上了当前硬阻断的 `trivial_pro_prompt_blocked`
- `report_v2` 改为：
  - `/v1/jobs` 固定用 `CHATGPTREST_API_TOKEN` Bearer
  - Gemini live proof 改用 `preset=auto + 实质性问题`

## Scope Boundary

- 这是 allowed low-level generic provider path proof
- 不是 direct `chatgpt_web.ask` 正常 live 路径证明
- 不是 qwen / 全 provider matrix
- 不是 full-stack deployment proof
