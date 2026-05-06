# Minimum Gap Closure List

| gap_id | missing_evidence | why_it_matters | temporary_handling | closure_condition |
|---|---|---|---|---|
| G1 | 一句 repo 级产品句子，以及 `ChatgptREST / OpenMind / OpenClaw` 的 authority matrix | 不先冻结“谁是什么”，后续任何 harness 目标都还会被多平面宿主现实冲散 | 暂以 `2026-04-01_chatgptrest_current_state_freeze_for_goal_discussion_v1.md` 为当前 mouthpiece | 产出 repo-level frozen sentence + plane owner matrix，并同步 README/AGENTS/关键 client docs |
| G2 | front-door / retirement matrix：`public MCP`、`/v3/agent/turn`、`/v2/advisor/*`、`/v1/jobs`、`/v1/tasks` 的 primary/default/maintenance 分类 | 不先冻结入口与退役边界，task runtime 无法判断自己是“主线候选”还是“永久旁路” | 当前默认继续视 `public MCP -> /v3/agent/turn` 为 public northbound，`/v1/tasks` 视为 incubating subsystem | 形成单表并在活动运维文档里统一，避免多份入口说明继续并存 |
| G3 | task runtime 是否被提升为“下一阶段 primary product track”的决策 | 这是目标讨论的真正分水岭；没这一步，文档会继续同时写“大主线”和“旁路线” | 暂时按 `strategic candidate but not default runtime` 处理 | 明确拍板后，只保留一套 roadmap：要么进入 next-stage mainline，要么降为长期 incubating subsystem |
| G4 | 若 task runtime 进入主线，需要一条真实 public lane 贯通 `task intake -> chunk contract -> evaluator -> publication -> distillation` | 现在能证明的多是旁路 `/v1/tasks` 子路径；没有真实主入口闭环，就不能宣称主线转移成功 | 暂不把 task runtime 写成 current completion authority | 至少一条真实 `/v3/agent/turn` lane 通过 task runtime 完成，并有回放证据、closeout 证据与系统级回归 |
| G5 | 真实 skeptical evaluator 证据：非 placeholder grader、artifact refs、fail-closed promotion | Anthropic harness 的核心不是“有 evaluation 字段”，而是 generator 不能自证完成 | 继续保守表述为 `promotion skeleton/foundation` | `_run_code_grader/_run_outcome_grader/_run_rubric_grader` 去 placeholder，且 negative tests 证明 promotion 无法绕过 |
| G6 | authoritative delivery/memory integration 证据：真实接通 `completion_contract/canonical_answer` 与 `work_memory_manager` | 没有真实下游 side effect，就不该占用 `PUBLISHED/DISTILLED` 这类强状态名 | 当前继续把 task runtime delivery/memory 视为 bridge/scaffold | 代码接线 + end-to-end evidence + rollback/failure tests 一起到位 |
| G7 | 缩小 acceptance ambition 的最小方案，而不是一次建设完整 mega-suite | 过大的 eval/harness 平台工程会反过来拖慢真正需要验证的主线 | 暂以 20-50 个真实任务/少量系统级 failure mode 为上限，优先验证最危险场景 | 建立小而硬的 acceptance subset：kill/recover、duplicate signal、evaluator reject、publication rollback、one live success lane |
| G8 | 对 `opencli / CLI-Anything` 的明确延期决议 | 这两条是最容易再次把目标包做大的地方 | 在下一阶段只保留 `validation POC / quarantine-shell` 口径，不纳入 primary milestone | 只有在 task runtime 主线闭环后，才允许单开下一轮受控升级讨论 |
