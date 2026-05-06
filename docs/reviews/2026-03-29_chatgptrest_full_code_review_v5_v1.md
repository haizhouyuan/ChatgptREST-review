# 2026-03-29 ChatgptREST Full Code Review v5 v1

> Review target: `HEAD=4dab82b`
> Reviewer: Codex
> Scope: `chatgptrest/`, `ops/`, `tests/`, `docs/ops/*`, `docs/dev_log/artifacts/*`
> Method: targeted pytest, code inspection, document-plane inspection, repository-shape inventory

## 1. 结论

这次 review 的结论不是“代码味道偏重”，而是：

- `master` 当前存在真实回归，且已经打到了公开 northbound 行为
- 文档平面和证据平面的边界虽然在 policy 里被写清了，但 repo 结构还没有跟上
- 配置、路径、运行边界和大文件热点仍然让仓库处于“可继续迭代，但修改成本和误伤风险偏高”的状态

最近一轮 skill-platform convergence 提交已经落在 `master`，但它们主要集中在 skill registry / market intake / standard entry signal，不覆盖这次 review 暴露的核心回归面。

## 2. 最高优先级发现

### CRITICAL-1: public `agent_v3` clarify gate 回归，scenario pack 在进入 strategist 前丢了关键字段

证据链：

- `chatgptrest/api/routes_agent_v3.py:2444-2450`
  - 先 `resolve_scenario_pack(...)`
  - 再 `apply_scenario_pack(...)`
  - 最后把 `context["scenario_pack"]` 设置成 `_scenario_pack_payload(scenario_pack)`
- `chatgptrest/advisor/scenario_packs.py:238-251`
  - `summarize_scenario_pack(...)` 只保留了 `scenario/profile/route_hint/output_shape/execution_preference`
  - 丢掉了 `clarify_questions` 和 `watch_policy`
- `chatgptrest/advisor/ask_strategist.py:162-180`
  - `_build_clarify_questions(...)` 明确依赖 `scenario_pack["clarify_questions"]`
- `chatgptrest/advisor/ask_strategist.py:184-229`
  - `_should_clarify(...)` 明确依赖 `scenario_pack["watch_policy"]["checkpoint"]`
- `tests/test_agent_v3_route_work_sample_validation.py:17-37`
  - 数据集要求会议纪要/访谈纪要/研究报告类样本走 `needs_followup + clarify`
  - 当前快照断言失败

复现结果：

- `./.venv/bin/pytest -q tests/test_agent_v3_route_work_sample_validation.py::test_phase9_agent_v3_route_dataset_passes -vv`
- 结果：`1 failed in 1.04s`
- 失败摘要：`report.num_failed == 3`，典型 mismatch 为
  - `expected_clarify_required: expected True, actual False`
  - `expected_controller_called: expected False, actual True`

影响：

- 公共 `advisor_agent_turn` 路径会把本应进入 clarify 的 ask 误送到 controller / report lane
- 这不是“文案偏差”，而是 northbound 决策语义回归
- 与 phase9 / phase11 数据集约束直接冲突

建议：

- `context["scenario_pack"]` 不能只存 summary projection
- 至少要把 strategist 依赖的 `clarify_questions`、`watch_policy`、以及任何 gate-sensitive 字段完整保留下来
- 修复后先回归 `phase9` 与 `phase11` 两组 validation，再考虑进一步裁剪 scenario-pack payload

### HIGH-1: `/v1/jobs` 在做 conversation/provider 语义校验前先触发 prompt policy，导致错误语义被遮蔽

证据链：

- `chatgptrest/api/routes_jobs.py:695-704`
  - `enforce_prompt_submission_policy(...)` 先于 `create_job(...)`
- `chatgptrest/core/job_store.py:400-447`
  - provider/thread 相关的 `conversation_url`、`parent_job_id`、kind mismatch 校验都在这里
- `chatgptrest/core/prompt_policy.py:220-239`
  - Pro trivial prompt 会直接抛 `trivial_pro_prompt_blocked`
- `tests/test_conversation_url_kind_validation.py:23-72`
  - 这些测试期待错误里出现 `gemini` / `chatgpt` / `qwen`
- `tests/test_conversation_url_conflict.py:72-122`
  - 这个测试本来要验证 Gemini thread rebind 语义，但 setup ask 在入口就被拦了

复现结果：

- `./.venv/bin/pytest -q tests/test_conversation_url_kind_validation.py::test_rejects_chatgpt_kind_with_gemini_conversation_url -vv`
- 结果：`1 failed in 1.42s`
- 实际返回：
  - `{"error":"trivial_pro_prompt_blocked", ...}`
- 预期是能看见 `gemini` 相关 kind/url mismatch

附加复现：

- `./.venv/bin/pytest -q tests/test_conversation_url_conflict.py::test_set_conversation_url_rebinds_gemini_thread_for_in_progress_followup -vv`
- 结果：`1 failed in 1.60s`
- 失败点：测试的第一个 `gemini_web.ask` 创建就返回 `400`，导致线程重绑逻辑根本没有被覆盖到

影响：

- API 返回的错误不再优先表达“请求语义错了”，而是表达“prompt policy 不允许”
- 一批 conversation/thread 状态机回归测试被入口政策遮蔽，导致真实语义面无法稳定回归

建议：

- 明确 `/v1/jobs` 的错误优先级
- 如果 contract / provider / thread 语义错误比 prompt policy 更基础，就先做语义校验再做 prompt policy
- 如果策略顺序不打算改，至少要把这些测试 fixture 改成非-trivial prompt，避免测试目标被遮蔽

### HIGH-2: `master` 当前不是 regression-closed 状态

直接证据：

- `./.venv/bin/pytest -x -vv`
  - 首个失败：`tests/test_agent_v3_route_work_sample_validation.py::test_phase9_agent_v3_route_dataset_passes`
  - 摘要：`1 failed, 165 passed`
- `./.venv/bin/pytest -vv --maxfail=8`
  - 在 `772 passed, 5 skipped` 后打出 8 个失败
  - 已确认的失败面包括：
    - `tests/test_agent_v3_route_work_sample_validation.py:17-37`
    - `tests/test_branch_coverage_validation.py:17-37`
    - `tests/test_conversation_url_conflict.py:72-122`
    - `tests/test_conversation_url_kind_validation.py:23-116`

判断：

- 这不是“偶发 flaky”
- 当前至少有两条真实语义面在回归：public clarify routing 与 `/v1/jobs` conversation/provider validation surface
- 任何继续叠加新能力、但不先收敛这两个回归面的做法，都会进一步放大验证噪声

## 3. 代码层面的治理问题

### MEDIUM-1: 包管理元数据不完整，`PyYAML` 处于“靠运行环境刚好有”的状态

证据：

- `pyproject.toml:1-36`
  - dependencies / optional-dependencies 中没有 `PyYAML`
- `chatgptrest/dashboard/service.py:16-19`
  - 运行时尝试导入 `yaml`
- `chatgptrest/kernel/topology_loader.py:121-138`
  - loader 明确依赖 `yaml.safe_load`
- `chatgptrest/finbot.py:2995-2999`
  - 运行时按需导入 `yaml`
- `tests/test_topology_contract.py:12-25`
  - 测试直接 `import yaml`

影响：

- 新环境、精简镜像、或只装声明依赖的 CI 容器里，会出现“代码能 import，package metadata 却没声明”的安装漂移
- 这类问题通常在最慢的地方爆雷：部署、临时 worker、或新同事首次拉起环境

建议：

- 把 `PyYAML` 明确写进依赖
- 同时把“没有 yaml 时 fallback”与“测试强依赖 yaml”之间的语义统一起来

### MEDIUM-2: 宿主机和外部 repo 路径被硬编码进产品代码，边界在代码层面被打穿

证据：

- `chatgptrest/dashboard/service.py:146-153`
  - 直接把 `finagent` repo 和本 repo `artifacts/finbot` 写死
- `chatgptrest/finbot.py:54-58`
  - `DEFAULT_FINAGENT_ROOT = Path("/vol1/1000/projects/finagent")`
- `chatgptrest/observability/__init__.py:27-30`
  - 直接把 `/vol1/maint/MAIN/secrets/credentials.env` 写入 `_CREDENTIALS_PATHS`

影响：

- 仓库从“可移植产品代码”退化成“当前主机拓扑上的工作副本”
- 在非 Yogas2、非同目录结构、或容器环境里，边界不再清晰
- dashboard/service 已经出现了对另一个 repo 文档结构的直接解析，属于产品代码与运维环境的耦合泄漏

建议：

- 把 cross-repo root 和 secrets path 收敛到 config / host profile / ops wrapper
- `chatgptrest/` 下的产品逻辑不要默认知道 `/vol1/...` 是什么
- 如果确实需要 host-specific fallback，也应经过显式 env/config，而不是直接硬编码

### MEDIUM-3: 配置面已经有 `AppConfig`，但大量模块仍然绕过它直接读环境变量

证据：

- `chatgptrest/core/config.py:39-104`
  - 已经定义了 `AppConfig` 和 `load_config()`
- 实际代码统计：
  - `chatgptrest/` + `ops/` 中 `os.environ.get` / `os.getenv` 命中 `475` 次
  - Top 负载文件包括：
    - `ops/maint_daemon.py` `70`
    - `chatgptrest/executors/repair.py` `28`
    - `chatgptrest/mcp/server.py` `24`
    - `chatgptrest/mcp/agent_mcp.py` `23`

影响：

- 默认值、兼容别名、host fallback、和 feature flag 的真实口径分散在几十个文件里
- review 时很难判断“某个 env 是 canonical config，还是局部绕过”
- 这类分散式 config 读取尤其容易让 northbound surface 与 systemd/ops 实际部署出现漂移

建议：

- 至少先把 API / MCP / worker / repair / maint-daemon 这些核心面做分层收敛
- 允许局部模块持有 feature flag，但要经过统一配置对象或统一 helper

### MEDIUM-4: 核心入口与运维脚本仍然过于单体化，局部修改风险过高

证据：

- `ops/maint_daemon.py` 共 `5466` 行，`main()` 位于 `ops/maint_daemon.py:2724`
- `chatgptrest/worker/worker.py` 共 `5415` 行，`_run_once()` 位于 `chatgptrest/worker/worker.py:2821`
- `chatgptrest/mcp/server.py` 共 `4059` 行，`chatgptrest_job_wait()` 位于 `chatgptrest/mcp/server.py:1555`
- `chatgptrest/api/routes_agent_v3.py` 共 `3245` 行，`agent_turn()` 位于 `chatgptrest/api/routes_agent_v3.py:2076`
- `chatgptrest/finbot.py` 共 `3208` 行

影响：

- 这类大文件会让“改一处、带出多条行为路径”的概率明显升高
- 评审、impact 分析、测试定界都会变难
- 这次 `agent_v3` clarify 回归，本质上就是高密度 orchestration 里很容易出现的上下文投影错误

建议：

- 优先拆入口编排，不急着先拆底层工具函数
- 先把“contract normalization / scenario-pack projection / branch decision / controller handoff”这类边界切出来

## 4. 文档治理问题

### DOC-1: 文档平面的 policy 已经存在，但证据平面仍然大量混在 repo docs 里，边界不够清晰

证据：

- `docs/ops/2026-03-25_document_plane_guide_v1.md:18-31`
  - 明确说明 `docs/dev_log/` 不是单一语义平面
- `docs/ops/2026-03-25_document_plane_guide_v1.md:84-101`
  - 明确把 `docs/dev_log/artifacts/*` 定义为 reference / evidence plane，不是 current guidance
- 当前 tracked 文件中，`docs/dev_log/artifacts/*` 共有 `247` 个条目

影响：

- 文档 policy 在“认知上”已经分层，但 repo 物理结构和索引边界还没有同步
- 维护者、搜索工具、代码图索引、以及 review 过程仍然会被大量历史证据文件噪声干扰

建议：

- 不要把这件事理解成“先删文件”
- 正确动作是先建立 evidence plane 的索引边界、入口索引和可搜索清单
- 当前 policy 也明确了这不是容量清理优先项

### DOC-2: 文件命名对人类可读，但对 shell/tooling 不友好，已经影响自动化操作

证据：

- docs 中存在空格文件名，例如：
  - `docs/Codex SDK 用法（Context7）.md`
  - `docs/OpenAI Codex 高阶技术落地案例.md`
- docs 中还存在大量超长路径，示例长度达到 `148` 字符，例如：
  - `docs/dev_log/artifacts/execution_experience_review_decision_scaffold_fixture_bundle_20260311/review_decision_scaffold_under_reviewed_v1_summary.json`

影响：

- 简单 shell 管道、批量打包、路径转义、以及某些审计脚本更容易踩坑
- 我这次做 repo inventory 时，基于 `git ls-files | xargs du` 的粗糙命令就被这类路径结构直接打断

建议：

- 对 current guidance / canonical docs 优先收敛更稳定的命名风格
- 对 evidence bundle 允许冗长，但最好同时生成一个短索引文件或 manifest

### DOC-3: review 结论的时效性没有显式治理

证据：

- 旧的 full review 文档仍在：
  - `docs/reviews/2026-03-02_chatgptrest_full_code_review_v4_CC.md`
- 但当前 `master` 已经出现新的回归面，旧 review 不再代表当前健康状态

影响：

- 新维护者如果只看到旧 review，可能会高估仓库当前稳定度
- “review 是历史快照还是当前 gate”在 repo 内没有统一 freshness 标识

建议：

- 对 review / audit 类文档增加“适用 commit / 失效条件 / 后继版本”字段
- `docs/README.md` 或 `docs/reviews/README` 可以维护一个当前有效 review 索引

## 5. 代码库治理问题

### REPO-1: GitNexus 索引已经落后于当前 `HEAD`

证据：

- `gitnexus://repo/ChatgptREST/context`
  - 返回：`Index is 38 commits behind HEAD`

影响：

- 代码图工具的 caller/callee / process / impact 结果存在时间漂移
- 对大仓库而言，这会直接降低 review、refactor 和 blast-radius 判断的可信度

建议：

- 把 analyze 刷新纳入 merge 后或每日例行治理
- 至少在做“全量 review / 大 refactor / 入口变更”前保证 index 同步到当前 head

### REPO-2: runtime 体量远大于源码体量，但治理动作还停留在 policy 层

证据：

- `docs/ops/2026-03-25_artifact_retention_policy_v1.md:25-39`
  - 已经记录 `artifacts/` 为 `160G`
- 实际盘点：
  - `artifacts/` `160G`
  - `state/` `1.2G`
  - `docs/` `12M`
  - `.git/` `80M`

判断：

- 当前容量压力不是 git 仓库本身，而是 runtime telemetry / monitor evidence
- policy 已经写明本轮不做清理，这个判断是对的；但治理 backlog 还没有被落成更强的 budget / archive / rotation 机制

建议：

- 先从 `artifacts/monitor/*` 和 `logs/*` 建 budget 与 archive 方案
- 不要误把 `docs/dev_log/artifacts/*` 当首要清理对象

### REPO-3: worktree 基线当前并不干净

证据：

- 当前 `git status --short` 仍有预存脏文件：
  - `docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322/report_v1.json`
  - `docs/dev_log/artifacts/phase11_branch_coverage_validation_20260322/report_v1.md`
  - `docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.json`
  - `docs/dev_log/artifacts/phase13_public_agent_mcp_validation_20260322/report_v1.md`
  - `docs/dev_log/artifacts/phase8_multi_ingress_work_sample_validation_20260322/report_v1.json`
  - `tests/test_repair_provider_tools.py`
- `.agents/workflows/task-closeout.md:7`
  - 明确写着 `Silent dirty state is treated as a defect`

影响：

- review baseline、回归判断、和提交边界更容易被混淆
- 这次我只能选择“只新增文档、不触碰既有脏文件”的保守路径

建议：

- 把 generated validation report 的落盘位置和 git tracking 策略再收敛一次
- 对长期脏文件建立 owner 和 pending reason，而不是让它们长时间悬空

## 6. 建议的治理顺序

### P0

- 修复 public `agent_v3` scenario-pack clarify/watch 字段丢失
- 明确 `/v1/jobs` 的错误优先级，修复 conversation/provider validation 被 prompt policy 遮蔽的问题
- 先把以下测试恢复为绿：
  - `tests/test_agent_v3_route_work_sample_validation.py`
  - `tests/test_branch_coverage_validation.py`
  - `tests/test_conversation_url_conflict.py`
  - `tests/test_conversation_url_kind_validation.py`

### P1

- 在 `pyproject.toml` 声明 `PyYAML`
- 收敛 host-specific path 到 config / ops wrapper
- 给 API / MCP / worker / repair 建统一 config 入口，减少分散的 env 读取

### P2

- 拆分 `maint_daemon`、`worker._run_once`、`agent_turn` 这类高风险大入口
- 给 evidence plane 建 manifest / index boundary，不以“删文件”作为第一动作
- 刷新 GitNexus index，并把 freshness 变成常规治理动作

## 7. 一句话判断

ChatgptREST 现在的主要问题不是“缺能力”，而是“入口编排复杂度、配置边界和证据平面边界已经超过当前治理强度”。如果不先收敛这几个点，后续每一轮新能力合入都会继续抬高 review 成本和误伤概率。
