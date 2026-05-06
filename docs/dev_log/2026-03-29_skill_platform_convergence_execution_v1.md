# Skill Platform Convergence Execution v1

更新时间：2026-03-29

## 1. 结论

这轮不是再做 skill platform 蓝图，而是按“收敛优先”的计划把现有主链往单一真相源、bundle-first runtime、受控外部 source、真实 usage signals 四个方向推进。

本轮完成了 4 个代码切片：

1. `advisor` compat layer 改成动态 canonical projection
2. OpenClaw runtime 明确把 `extraDirs` 降成 bundle 驱动的 materialization/fallback
3. skill market 加入 allowlisted source intake
4. `advisor.standard_entry` 在真实 skill 解析命中时补发 `skill.selected`

## 2. 提交

1. `0a49549` `refactor: converge advisor skill registry to dynamic canonical projection`
2. `434fb6a` `refactor: make openclaw skill dirs bundle-driven fallback`
3. `6f7f078` `feat: add allowlisted skill market source intake`
4. `727507e` `feat: emit selected skill signals from standard entry`

## 3. 结果

### 3.1 advisor compat layer

- `chatgptrest/advisor/skill_registry.py` 继续保留为 compat wrapper
- `SKILL_CATALOG` / `TASK_SKILL_REQUIREMENTS` / `DEFAULT_AGENT_PROFILES` 改为动态 registry-backed projection
- legacy compat 分支的 authority mode 改为 `compat_profile_projection`

### 3.2 OpenClaw runtime

- `scripts/rebuild_openclaw_openmind_stack.py` 不再无条件挂 `skills-src`
- 只有 active bundles 需要 runtime-local skill materialization 时，才会把 repo-local `skills-src` 加入 `extraDirs`
- 这让 `extraDirs` 更接近 fallback/materialization，而不是主能力源

### 3.3 外部 source intake

新增：

- `ops/policies/skill_market_sources_v1.json`
- `ops/import_skill_market_candidates.py`
- `ops/manage_skill_market_candidates.py` 的：
  - `list-sources`
  - `import-source`

行为：

- 按 allowlisted source 导入候选
- 只支持 quarantine candidate intake
- 按 `(skill_id, source_market, source_uri)` 去重

### 3.4 usage signals

- `chatgptrest/advisor/standard_entry.py` 现在在 skill check 通过时，会根据 canonical registry 解析并发出 `skill.selected`
- 这让 `advisor.standard_entry` 成为真实 resolution lane，而不只是推荐 lane

## 4. 验证

本轮定向回归：

```bash
/vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_system_optimization.py \
  tests/test_phase3_integration.py \
  tests/test_rebuild_openclaw_openmind_stack.py \
  tests/test_import_skill_market_candidates.py \
  tests/test_manage_skill_market_candidates.py \
  tests/test_market_gate.py
```

相关 `py_compile` 也已逐切片执行。

## 5. 剩余未做

这轮仍未做的主要项：

1. 让 `advisor/skill_registry.py` 进一步减少 compat override 面
2. 给官方 registry / curated GitHub / 中文生态补真实 source adapter
3. 让更多 execution lane 稳定上报 usage signals

## 6. 一句话收口

本轮完成的不是“从零搭 skill platform”，而是把已经存在的主链继续收敛：更少的第二套真相源、更明确的 bundle-first runtime、受控的 market source intake、以及更真实的 usage signals。
