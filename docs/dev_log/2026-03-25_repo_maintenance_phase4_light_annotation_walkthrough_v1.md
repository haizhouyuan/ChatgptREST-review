# ChatgptREST Repo Maintenance Phase 4 Light Annotation Walkthrough v1

> 日期: 2026-03-25
> 范围: primary / admin / internal entrypoint 轻量标记
> 结果: 完成注释与入口引导补强，无运行时行为改动

## 1. 本轮落地内容

本轮只做两类低风险动作：

- 在根 `README.md` 增加 maintainer quick links
- 在真实入口脚本头部补充分类注释

涉及文件：

- `README.md`
- `ops/start_mcp.sh`
- `ops/start_api.sh`
- `ops/start_driver.sh`
- `ops/start_worker.sh`
- `ops/start_admin_mcp.sh`
- `ops/chrome_start.sh`

## 2. 标记后的口径

本轮把入口语义直接贴到脚本头部，避免新 agent 只看文件名就误入：

- `ops/start_mcp.sh`
  - primary coding-agent northbound surface
- `ops/start_api.sh`
  - primary runtime API entry
- `ops/start_driver.sh`
  - internal driver MCP entry
- `ops/start_worker.sh`
  - runtime-plane worker entry
- `ops/start_admin_mcp.sh`
  - admin-only broad MCP surface
- `ops/chrome_start.sh`
  - internal driver lane bootstrap
  - `.run/` 与 browser profile 属于 live runtime state，不按 cleanup 对象处理

## 3. 为什么这轮安全

本轮没有做以下事情：

- 没有改 shell 参数解析
- 没有改任何启动命令
- 没有改环境变量默认值
- 没有改端口
- 没有改 systemd
- 没有改 worker / API / MCP / advisor 的代码分支
- 没有删除 worktree、目录、artifact tree
- 没有处理 `.run/*`、`state/*`、`artifacts/jobs/*`、`artifacts/monitor/*`

因此本轮属于：

- docs-only
- guidance-only
- comment-only entrypoint labeling

## 4. 与前序 policy 的对齐

这轮执行和既有计划保持一致：

- 延续 `docs/ops/2026-03-25_entrypoint_matrix_v1.md` 的分类口径
- 延续 `docs/ops/2026-03-25_artifact_retention_policy_v1.md` 对 `.run/` 的 live runtime state 定义
- 延续 `docs/ops/2026-03-25_agent_maintainer_entry_v1.md` 的默认入口教学

## 5. 一句话结论

> Phase 4 的首轮执行只把“入口是什么、哪些不是默认入口、哪些目录不能按清理思路处理”直接写到 README 和脚本头部，没有任何运行时逻辑改动。
