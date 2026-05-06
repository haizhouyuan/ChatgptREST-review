# Skill Platform Convergence Execution Walkthrough v1

更新时间：2026-03-29

## 做了什么

### Slice 1

- 调整 `chatgptrest/advisor/skill_registry.py`
- 保留 compat layer 文件本身
- 将默认 skill/task/profile 表改成 canonical registry 的动态 projection

### Slice 2

- 调整 `scripts/rebuild_openclaw_openmind_stack.py`
- 让 `skills.load.extraDirs` 只在 active bundles 需要 runtime-local skill materialization 时出现
- 增加对应测试，验证“无 runtime-local bundle 时不挂 repo-local skill dir”

### Slice 3

- 新增 `ops/policies/skill_market_sources_v1.json`
- 新增 `ops/import_skill_market_candidates.py`
- 扩展 `ops/manage_skill_market_candidates.py`
- 新增测试覆盖 allowlisted source import 和去重

### Slice 4

- 调整 `chatgptrest/advisor/standard_entry.py`
- 在通过的 skill resolution 路径补发 `skill.selected`
- 新增测试验证标准入口现在会留下 selected signal

## 为什么这么做

这轮目标不是再证明 skill platform 不是 0，而是把现有主链继续收敛：

1. advisor 兼容层不再维护第二套默认表
2. OpenClaw runtime 更明确地以 bundle 为主，以 repo-local dirs 为 fallback/materialization
3. market gate 有了真正受控的外部候选导入面
4. usage signals 更靠近真实解析/执行路径，而不是只停在 market gate 或 runtime sync

## 验证怎么做

逐切片执行：

- `py_compile`
- 定向 `pytest`
- staged `gitnexus_detect_changes()`

并按仓库要求每个有意义切片单独提交。

## 当前边界

这轮没有做：

- 自动安装第三方 skill
- 任意来源 market crawl
- 移除 OpenClaw `extraDirs`
- 改 worker / routes_jobs / agent_mcp 运行逻辑

## 下一步

下一轮最值得做的是：

1. 继续压缩 advisor compat override 面
2. 补真实官方/curated/中文生态 source adapters
3. 把 usage signals 接到更多真实 execution lane
