# 2026-03-21 Phase 2 Ingress Alignment Completion v2

## 1. 为什么要出 v2

[2026-03-21_phase2_ingress_alignment_completion_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_phase2_ingress_alignment_completion_v1.md)
把 live ingress alignment 主结论写对了，但 review 抓到了两个剩余语义缺口：

1. OpenClaw plugin 对未覆盖 `goal_hint` 默认压 `general`
2. `/v2/advisor/advise` 对 `task_intake.attachments` 仍有损

这两个点已经在：

- [2026-03-21_task_intake_phase2_gap_fixes_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-21_task_intake_phase2_gap_fixes_v1.md)

里补掉，所以 `v2` 可以给出更准确的阶段结论。

## 2. 阶段结论

`Phase 2: Ingress Alignment` 现在可以按更强口径签字：

- live ingress adapter alignment complete
- canonical payload semantics for current live lanes are no longer lossy

换句话说，`Phase 2` 的阻断点已经不在 front-door object 本身，而只剩 legacy / migration 问题。

## 3. 当前真实状态

### 3.1 已完成

- OpenClaw plugin 显式发送 versioned `task_intake`
- Feishu WS 显式发送 versioned `task_intake`
- `/v2/advisor/advise` 真正消费 versioned `task_intake`
- `planning` goal hint 不再被 OpenClaw adapter 压成 `general`
- `task_intake.attachments` 不再在 advise lane 丢失

### 3.2 未完成但不阻断 Phase 2

- Feishu WS 仍未迁到 `/v3/agent/turn`
- `/v1/advisor/advise` 仍保留 legacy compatibility
- public front door 仍兼容 scattered top-level fields
- mixed MCP/CLI callers 还没全部显式发 `task_intake`

这些是 legacy retirement / migration 问题，不再是 Phase 2 的 canonical ingress problem。

## 4. 回归

本轮修订后，通过了：

```bash
./.venv/bin/pytest -q tests/test_task_intake.py tests/test_routes_advisor_v3_task_intake.py tests/test_routes_agent_v3.py tests/test_agent_v3_routes.py tests/test_system_optimization.py tests/test_system_optimization_v2.py tests/test_openclaw_cognitive_plugins.py tests/test_feishu_ws_gateway.py tests/test_business_flow_advise.py tests/test_advisor_v3_end_to_end.py -k 'task_intake or advise or feishu or openclaw or StandardEntry or v3_ask_'
python3 -m py_compile chatgptrest/advisor/task_intake.py chatgptrest/advisor/feishu_ws_gateway.py tests/test_task_intake.py tests/test_routes_advisor_v3_task_intake.py tests/test_openclaw_cognitive_plugins.py
```

## 5. 下一步

Phase 2 现在可以真正结束，下一步应进入：

- `Phase 3: Planning Scenario Pack`

而不是继续在 ingress semantics 上反复打补丁。
