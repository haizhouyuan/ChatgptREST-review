# ChatgptREST 低风险仓库整顿与维护入口收口计划 v1

> 日期: 2026-03-25
> 状态: draft for review
> 基线: `75ff09d33606` (`2026-03-25 75ff09d Document public MCP wrapper handoff fixups`)

## 1. 任务定义

本轮目标不是“重构 ChatgptREST”，而是：

- 做一轮低风险的仓库整顿与维护入口收口
- 提升新 agent 的可维护性、可接手性、可判断性
- 不改变核心运行时行为，不触碰既有 public contract 语义

本轮明确非目标：

- 不做大功能开发
- 不改 public contract 语义
- 不改默认端口、systemd 行为、运行时拓扑
- 不顺手修 unrelated bug
- 不把 finagent / openclaw / chatgptMCP 一起拉进重构
- 不删除任何 worktree，除非先产出清单并单独确认
- 不处理当前主仓已知 4 个历史 validation artifact 脏文件

本轮只允许优先处理 4 类事：

1. 维护入口文档收口
2. worktree / 残留目录盘点与分类
3. `artifacts/` / `.run/` / `docs/dev_log/` / `docs/dev_log/artifacts/` 的保留策略梳理
4. deprecated / primary entrypoint 的文档化和轻量标记

## 2. 本轮调查输入

按要求已先读：

1. `AGENTS.md`
2. `docs/runbook.md`
3. `docs/contract_v1.md`
4. `docs/client_projects_registry.md`
5. `docs/handoff_chatgptrest_history.md`
6. `docs/dev_log/2026-03-25_chatgptrest_agent_maintainer_entry_map_v1.md`

为避免重复设计，还额外核对了：

- `README.md`
- `docs/README.md`
- `docs/2026-03-17_mcp_and_api_surface_inventory_v1.md`
- `docs/2026-03-17_public_agent_mcp_default_cutover_v1.md`
- `docs/2026-03-16_finbot_continuous_runtime_rollout_v2.md`
- `docs/roadmaps/2026-03-16_artifact_governance_blueprint_v2.md`

## 3. 只读调查结论

### 3.1 仓库现状不是“一个服务”，而是多平面叠加

当前至少有 5 个维护判断平面：

| Plane | 代表入口 | 当前作用 | 本轮风险判断 |
|---|---|---|---|
| Execution plane | `routes_jobs.py` / `worker.py` | `/v1/jobs`、send/wait、artifact 落盘 | 高风险，首轮禁改行为 |
| Public agent surface | `agent_mcp.py` / `routes_agent_v3.py` | coding-agent 默认 northbound 面 | 高风险，首轮只做文档收口 |
| Advisor plane | `routes_advisor_v3.py` / `chatgptrest/advisor/*` | OpenMind / report / funnel / memory | 中高风险，首轮不扩改 |
| Controller / finbot plane | `ops/openclaw_*` / `finbot.py` | guardian / orch / finbot / lane continuity | 中高风险，首轮只读 |
| Dashboard plane | `app_dashboard.py` / `state/dashboard_control_plane.sqlite3` | operator read model | 中风险，首轮只做入口澄清 |

结论：

- `docs/README.md` 是通用文档索引，不是维护者决策入口
- `docs/dev_log/2026-03-25_chatgptrest_agent_maintainer_entry_map_v1.md` 已经是很好的 seed，但还不是正式 canonical maintainer entry
- `docs/2026-03-17_mcp_and_api_surface_inventory_v1.md` 提供了 surface inventory，但仍带有一部分历史/过渡语义，不适合继续直接当“新 agent 默认入口”

### 3.2 默认入口已经发生切换，但入口文档仍分散

当前稳定结论已经比较一致：

- coding agent 默认入口是 public advisor-agent MCP：`http://127.0.0.1:18712/mcp`
- 默认工具是 `advisor_agent_turn` / `advisor_agent_status` / `advisor_agent_cancel`
- `/v1/jobs kind=*web.ask` 对 coding agent 已不是默认入口
- `/v3/agent/*` 是 backend ingress，不是推荐 northbound default surface
- admin/internal MCP 与 legacy broad surface 仍然存在，但应该明确为 ops/debug 用途

问题不在“没有结论”，而在：

- 结论分散在 `AGENTS.md`、`runbook.md`、`contract_v1.md`、`client_projects_registry.md`、`dev_log` 文档
- 历史 inventory 文档仍保留旧工具面叙述，容易让新 agent 误以为 broad MCP 仍是推荐入口

### 3.3 worktree 现实比现有 entry map 更复杂

当前 `git worktree list --porcelain` 统计结果：

- 主 worktree：`1`
- repo 内或 repo 邻近 worktree：`28`
- `/vol1/1000/worktrees/` 下稳定 worktree：`13`
- `/tmp/` 下临时 worktree：`34`
- 其他前缀：`5`
- detached worktree：`5`

当前 worktree 不是单一模式，而是混合了：

1. 主仓 authoritative checkout
2. repo 内 `.worktrees/*` 型开发/验证 worktree
3. `/vol1/1000/projects/ChatgptREST-*` 邻近目录型 worktree
4. `/vol1/1000/worktrees/chatgptrest-*` 稳定部署或独立任务 worktree
5. `/tmp/chatgptrest-*` 临时 scratch / review / merge / validation worktree
6. 少量 detached / 其他路径残留

关键风险：

- 历史上确实存在 systemd/runtime 指向 stable worktree 的事实
- 因此不能把所有非主仓 worktree 一概视为“可删垃圾”
- 首轮应先分类，不应直接清理

### 3.4 artifact 盘面已经出现明显主次失衡

当前大致体量：

- `artifacts/`: `160G`
- `state/`: `1.2G`
- `.run/`: `23M`
- `logs/`: `8.0M`
- `docs/dev_log/`: `7.1M`
- `docs/dev_log/artifacts/`: `2.5M`

更关键的是分布：

- `artifacts/monitor/`: `128G`
- `artifacts/jobs/`: `7.7G`
- `artifacts/finbot/`: `33M`
- `state/driver/`: `12M`
- `state/sre_lanes/`: `84K`

`artifacts/monitor/` 内部热点：

- `artifacts/monitor/maint_daemon`: `120G`
- `artifacts/monitor/periodic`: `6.0G`
- `artifacts/monitor/planning_review_plane_refresh`: `1.5G`

而文档侧：

- `docs/dev_log/` 顶层文件数：`833`
- `docs/dev_log/artifacts/` 子目录数：`49`
- `docs/` 顶层文件数：`78`
- `docs/reviews/` 顶层文件数：`98`
- `artifacts/jobs/` job 目录数：`8032`

结论：

- 首要 retention 风险不在 `docs/dev_log/artifacts`
- 真正的大头是 runtime monitor 产物，尤其 `maint_daemon`
- `docs/dev_log/artifacts` 更像审计/验证包，体积小，但命名和语义需要分层

### 3.5 关联库边界清楚，但需要在 maintainer 文档里显式冻结

| Repo | 路径 | 当前角色 | 本轮默认策略 |
|---|---|---|---|
| finagent | `/vol1/1000/projects/finagent` | research engine / finbot 上游 | 只读 |
| openclaw | `/vol1/1000/projects/openclaw` | orchestration 母体 | 只读 |
| chatgptMCP | `/vol1/1000/projects/chatgptMCP` | legacy external fallback | 只读 |

首轮计划必须把这三者写进 maintainer entry / worktree policy，而不是只散落在 `AGENTS.md`。

### 3.6 当前必须冻结的区域

根据任务约束，本轮应显式列为“首轮不碰”的有：

- `chatgptrest/worker/worker.py`
- `chatgptrest/api/routes_jobs.py`
- `chatgptrest/mcp/agent_mcp.py`
- `finagent` / `openclaw` / `chatgptMCP` 代码
- systemd 行为、端口、运行时拓扑
- 当前主仓 4 个历史 validation artifact 脏文件：
  - `docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322/report_v1.json`
  - `docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322/report_v1.md`
  - `docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.json`
  - `docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.md`

## 4. 现阶段真正的问题

本轮不是在解决“功能缺失”，而是在解决“接手成本过高”：

1. 新 agent 无法在 5-10 分钟内判断自己该进哪个 plane。
2. worktree 生态太杂，但没有一份当前有效的分类与使用规则。
3. retention 相关已有蓝图，但没有面向 maintainer 的简化可执行 policy。
4. deprecated / retired / maintenance-only / admin-only 入口没有被统一标成一个体系。

## 5. 本轮成功标准

第一轮只追求这 3 个结果：

1. 新 agent 知道从哪进。
2. 大家知道哪些目录是活的、哪些是历史残留。
3. 大家知道哪些东西能删、哪些绝对别碰。

对应验收标准：

- 新 agent 能在 5-10 分钟内判断自己该进哪个 plane
- worktree / 历史残留有分类清单
- cleanup backlog 被拆成 `低风险 / 需确认 / 高风险` 三类

## 6. 建议交付物与落点

本轮建议至少交 5 份文档性产物：

| 交付物 | 目的 | 建议位置 | 说明 |
|---|---|---|---|
| Repo entry map | 正式 maintainer entry | `docs/2026-03-25_agent_maintainer_entry_v1.md` | 把现有 entry map 从 dev_log 提升为正式入口 |
| Worktree inventory | worktree 分类与行为边界 | `docs/ops/2026-03-25_worktree_policy_v1.md` | 先分类、后提案，不做删除 |
| Artifact retention policy | runtime/doc artifact 保留策略 | `docs/ops/2026-03-25_artifact_retention_policy_v1.md` | 先写 policy，不上自动清理 |
| Cleanup backlog | 拆分后续动作优先级 | `docs/dev_log/2026-03-25_repo_cleanup_backlog_v1.md` | 低风险 / 需确认 / 高风险 |
| Walkthrough | 记录本轮调查与执行 | `docs/dev_log/2026-03-25_repo_maintenance_round1_walkthrough_v1.md` | 满足 closeout 记录要求 |

说明：

- 这些文件名是建议落点，不是要求本轮一次性全部实现
- 本次提交应先做“计划文档 + walkthrough”
- 其余交付物待 plan 审核通过后再分批实现

## 7. 推荐执行顺序

### Phase 0: 审核并冻结边界

目标：

- 审核本计划
- 明确本轮只做低风险文档收口
- 明确不触碰运行面行为逻辑

输出：

- 本计划文档

### Phase 1: Maintainer Entry 收口

只做：

- 把现有 `entry_map_v1` 升级为正式 maintainer entry 文档
- 写清楚 plane 判断矩阵、默认入口、禁止入口、关联库边界
- 统一 cross-link 到 `AGENTS.md` / `docs/README.md` / `runbook.md`

不做：

- 改 MCP/REST 行为
- 改 client contract
- 顺手修 surface bug

验证：

- 文档内部链接可追溯
- “默认入口 / maintenance-only / admin-only / retired” 语义一致

### Phase 2: Worktree Inventory / Policy

只做：

- 建立 worktree 分类规则
- 区分主仓、稳定部署 worktree、开发 worktree、临时 `/tmp` worktree、未知残留
- 标出“只允许提案、不允许直接删”的类别

不做：

- 删除任何 worktree
- 调整 systemd drop-in 指向
- 迁移运行中 lane

验证：

- `git worktree list` 中每类都有归属
- 能明确哪些路径可能仍是 deployment root

### Phase 3: Artifact Retention Policy

只做：

- 基于现有 `artifact_governance_blueprint_v2` 收敛出“维护者可执行版”
- 把 `artifacts/`、`.run/`、`docs/dev_log/`、`docs/dev_log/artifacts/` 分成不同 retention class
- 明确 runtime canonical evidence 与 validation/review pack 的不同口径

建议分类起点：

1. Runtime canonical evidence
   - `artifacts/jobs/*`
   - `artifacts/monitor/maint_daemon/incidents/*`
2. Runtime rolling telemetry
   - `artifacts/monitor/*`
   - `.run/*`
   - `logs/*`
3. Validation / review packs
   - `docs/dev_log/artifacts/*`
   - `artifacts/reviews/*`
   - `artifacts/release_validation/*`
4. Historical development docs
   - `docs/dev_log/*`

不做：

- 上自动删除脚本
- 直接清空大目录
- 改运行时 artifact 落盘逻辑

验证：

- 每类目录都有“保留原因 / 可清理条件 / 禁止动作”
- 文档能解释为什么 `monitor` 是当前主要风险源，而不是 `docs/dev_log/artifacts`

### Phase 4: Deprecated / Primary Entrypoint 标记

只做：

- 做一张入口矩阵：`primary / admin / maintenance-only / legacy fallback / retired`
- 优先在文档和入口脚本注释上标记，而不是改行为

建议优先标记对象：

- public/default MCP entrypoint
- admin/internal MCP entrypoint
- maintenance-only legacy jobs path
- retired legacy orch topology
- external chatgptMCP fallback path

注意：

- 如果要修改任何函数 / 类 / 方法的注释附近代码，先跑 GitNexus impact
- 首轮不修改 `agent_mcp.py` / `routes_jobs.py` / `worker.py`

### Phase 5: Cleanup Backlog 提案

只做：

- 输出 backlog 清单
- 分成 `低风险 / 需确认 / 高风险`
- 把“可删建议”与“不可删目录”分离

不做：

- 批量删除
- 自动归档
- 改动运行态数据根

## 8. 后续低风险改动建议边界

本计划审核通过后，首轮低风险改动应限制在：

- 新增文档
- 现有文档 cross-link 收口
- `.gitignore` / 目录说明 / README 指引类修改
- 入口脚本的轻量注释或说明性标记

仍不建议首轮直接做的事情：

- 任何 worker / routes / agent surface 行为调整
- deployment worktree 迁移
- runtime retention 自动执行
- finbot / openclaw / chatgptMCP 跨仓修复

## 9. 建议提交粒度

计划获批后，推荐按下面粒度提交：

1. `docs: add official maintainer entry doc`
2. `docs: add worktree policy and inventory`
3. `docs: add artifact retention policy`
4. `docs: mark primary vs deprecated entrypoints`
5. `docs: add cleanup backlog and walkthrough`

每个提交前都要：

- 跑 `gitnexus_detect_changes()`
- 确认未带上那 4 个历史脏文件
- 避免把 unrelated runtime residue 混进提交

## 10. 本计划对已有文档的处理原则

以下文档视为“继承基础”，不覆盖：

- `docs/dev_log/2026-03-25_chatgptrest_agent_maintainer_entry_map_v1.md`
- `docs/2026-03-17_mcp_and_api_surface_inventory_v1.md`
- `docs/roadmaps/2026-03-16_artifact_governance_blueprint_v2.md`

本轮做法应是：

- 抽取有效结论
- 写成 maintainer-facing 的简化版政策/入口文档
- 明确哪些旧文档是 `history/proposal/reference`，哪些是 `current canonical guidance`

## 11. 我建议的最终一句话入口

如果只允许给新维护 agent 一句话：

> 先判断任务属于 execution plane、public agent surface、advisor plane、controller/finbot plane 还是 dashboard plane；默认从 public advisor-agent MCP 和 maintainer entry 文档进，不要从低层 `/v1/jobs` 或历史 broad MCP 面开局。

## 12. 待你审核的决策点

我希望你重点审核这 5 件事：

1. 本轮交付是否以“计划文档 + 后续分批实现”作为节奏，而不是一次做完全部收口。
2. 正式 maintainer entry 文档是否放到 `docs/` 根，而不是继续停留在 `docs/dev_log/`。
3. worktree policy 是否明确把 `/vol1/1000/worktrees/` 视为“可能承载稳定部署”的特殊类别。
4. artifact retention policy 是否把主要治理焦点放在 `artifacts/monitor/`，而不是 `docs/dev_log/artifacts/`。
5. deprecated / primary entrypoint 标记首轮是否只做文档和轻量注释，不碰运行行为。
