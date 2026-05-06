## Goal

完成 Planning 主线正式用户闭环验收：证明一个真实用户通过正式入口（Feishu / OpenClawBot → openmind_advisor_ask）发起一次真实 planning 工作，拿到可用产出，并将该产出实际用于推进工作。这是 v67 execution master 明确标注的唯一剩余缺口。

## Plan

### Step 1 — 通过正式入口发起一次真实 planning 任务并拿到完整答案

通过 OpenClawBot 正式 tool surface（`openmind_advisor_ask`）提交一个真实的 planning 请求（非 smoke / 非 demo），等待 backend 返回 `completed` 状态，并确认 plugin 出口展示的是 answer-first 人话内容。

过线判断：

- `openmind_advisor_session_get` 返回 `status=completed`，`next_action` 无 `same_session_repair`
- 用户侧看到的首屏内容是答案正文，不含 Route / Session / Run 等机器元数据
- 对应 task 在 `openmind_advisor_task_get` 上可查且 `quality_gate` 通过

### Step 2 — 将 planning 产出实际用于推进一项具体工作

将 Step 1 拿到的 planning 输出作为输入，驱动至少一个后续动作（例如：据此创建实施 PR、据此拆分子任务、据此启动 coding_agent 执行）。该后续动作必须产生可审计的工件（commit / task / artifact）。

过线判断：

- 存在至少一个可审计工件（git commit / task record / 文件产物）其来源可追溯到 Step 1 的 planning 输出
- 该工件不是为了验收而造的 demo，而是对项目有实际推进价值

### Step 3 — 固化证据并提交闭环验收记录

将 Step 1–2 的完整证据链（session artifact、task snapshot、后续工件引用）归档到 `docs/dev_log/artifacts/` 下，撰写正式验收 review 文档并提交。

过线判断：

- `docs/dev_log/artifacts/planning_user_loop_acceptance_<date>/manifest.json` 包含 session_id、task_id、后续工件引用
- `docs/reviews/` 下存在对应的正式验收 review 文档，结论为 accepted 且明确标注 boundary
- `planning_agent_total_plan_execution_master` 升版，将“正式入口真实工作闭环”从剩余缺口移入已证明范围
- `pytest -q` 全量通过，无新增 regression

## Dependencies

| 依赖 | 说明 |
|------|------|
| OpenClawBot 正式 tool surface 可用 | `openmind_advisor_ask` 等 5 个 tool 必须在线且路由正常 |
| ChatgptREST API + Driver 服务在线 | planning backend 必须能正常接收和执行作业 |
| 至少一条执行 lane 可用 | `web` 或 `coding_agent` 至少一条不处于 cooldown / blocked |
| 真实 planning 需求存在 | 必须有一个当前项目中实际需要做的 planning 工作，不能是纯 demo |

## Risks

| 风险 | 影响 | 缓解 |
|------|------|------|
| ChatGPT driver 在 send 阶段再次 timeout / blocked | Step 1 无法拿到 completed 答案 | 已有 fail-close 投影（v67 已证明）；可切换到 Gemini lane 重试 |
| planning 输出质量不足以直接驱动后续工作 | Step 2 无法产生有实际价值的工件 | 允许在同一 session 内 continue 补充；若仍不足则如实记录为 boundary |
| 验收过程中 backend 代码发生变更导致行为漂移 | 证据链断裂 | 验收期间冻结 planning 相关代码路径，仅允许验收记录类提交 |

## Validation

1. Step 1 的 session artifact 中 `status=completed` 且 plugin 出口无机器元数据泄露
2. Step 2 产生的工件有 git commit 或等价审计记录，且可追溯到 Step 1 session
3. Step 3 的 review 文档通过 Claude 审查，execution master 升版后 boundary 声明与实际证据一致
4. `pytest -q` 全量通过
5. `gitnexus_detect_changes` 确认变更范围仅限验收记录文件，无意外代码改动
