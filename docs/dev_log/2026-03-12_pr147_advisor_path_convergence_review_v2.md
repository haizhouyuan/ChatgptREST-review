# PR #147 Review v2: Advisor Path Convergence

**Reviewer**: Codex  
**Date**: 2026-03-12  
**Branch**: `codex/advisor-path-convergence-20260312`  
**PR**: `#147 feat: converge advisor metadata and harden openmind async flow`

---

## 结论

**需要修正后再合入。**

这条 PR 的主方向是对的，但当前版本至少有 3 个需要先收口的问题：1 个明显兼容性回归，1 个长答案截断缺陷，1 个 metadata 收敛不完整。

---

## Findings

### 1. `HIGH` OpenClaw `openmind-advisor` 的默认行为已经从“返回结果”变成“默认只提交作业”，这是外部兼容性回归

证据：

- 默认模式从 `advise` 改成了 `ask`：[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/openclaw_extensions/openmind-advisor/index.ts#L29)
- 执行时若调用方没传 `mode`，会直接落到 `ask`：[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/openclaw_extensions/openmind-advisor/index.ts#L306)
- `ask` 分支默认 `waitForCompletion=false`，因此不会等待最终答案：[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/openclaw_extensions/openmind-advisor/index.ts#L312)
- 真正等待结果只发生在显式 `waitForCompletion=true` 时：[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/openclaw_extensions/openmind-advisor/index.ts#L368)
- 插件 manifest 版本没有同步提升，仍是 `2026.3.8`：[openclaw.plugin.json](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/openclaw_extensions/openmind-advisor/openclaw.plugin.json#L5)

影响：

- 之前省略 `mode` 的调用方，原本能拿到同步结构化回答；现在默认只能拿到 `submitted + job_id`
- 这不是“纯新增字段”，而是默认交互语义变化
- PR 说明把它表述成 additive hardening，但对已有 OpenClaw tool caller 来说，这是 breaking change

建议：

- 要么恢复默认 `advise`，把 async `ask` 作为显式 opt-in
- 要么保留默认 `ask`，但在不传 `mode` 时自动 `waitForCompletion=true`
- 二选一都比“默认变异步但不等结果”更安全

### 2. `HIGH` 插件长任务完成后只抓第一段 answer chunk，长报告会被静默截断

证据：

- `waitForAdvisorJob()` 在完成后只请求一次 `/v1/jobs/{job_id}/answer?max_chars=16000`：[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/openclaw_extensions/openmind-advisor/index.ts#L222)
- 读取后直接把第一段 `chunk` 赋给 `merged.answer`，没有继续按 `next_offset` 翻页：[openmind-advisor/index.ts](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/openclaw_extensions/openmind-advisor/index.ts#L230)
- 服务端 `AnswerChunk` 明确就是分片协议，包含 `next_offset` 和 `done`：[schemas.py](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/chatgptrest/api/schemas.py#L121)

影响：

- 这条 PR 正在把插件朝 report / deep research / 长任务方向推进
- 但一旦答案超过 16000 字符，插件会无提示地返回不完整内容
- 这会直接破坏“等待最终答案”的核心场景，而且调用方很难发现自己拿到的是残缺结果

建议：

- 在插件里循环拉取 `/answer` 直到 `done=true`
- 如果暂时不做循环，至少要在结果里显式暴露 `truncated=true` 或 `next_offset`

### 3. `MEDIUM` `/v2/advisor/advise` 的 `request_metadata.trace_id` 不是有效执行 trace，metadata 收敛并未真正完成

证据：

- `advise()` 在调用 `api.advise()` 之前就把 `request_metadata` 固化了：[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/chatgptrest/api/routes_advisor_v3.py#L455)
- 如果请求里没有 `trace_id`，这里记录的就是空字符串：[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/chatgptrest/api/routes_advisor_v3.py#L453)
- 但 `AdvisorAPI.advise()` 会在没有传入 trace 时自行生成新的 `trace_id`：[advisor_api.py](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/chatgptrest/advisor/advisor_api.py#L88)
- 返回响应时又只是 `setdefault("request_metadata", request_metadata)`，不会把真正生效的 trace 回填进去：[routes_advisor_v3.py](/vol1/1000/projects/ChatgptREST/.worktrees/advisor-path-convergence-20260312/chatgptrest/api/routes_advisor_v3.py#L533)

影响：

- `ask` 路径现在能稳定回传有效 `trace_id`
- 但 `advise` 路径在最常见的“未显式传 trace_id”场景下，`request_metadata.trace_id` 会是空的
- 这让“统一 metadata echo”只完成了一半，也会误导后续排障与日志检索

建议：

- 在 `api.advise()` 返回后，用实际返回的 `trace_id` 回填 `request_metadata`
- 或者把 `request_metadata` 明确改名成 `request_echo`，避免被误解为“已生效执行元数据”

---

## 与旧 review 的分歧

现有无版本 review 文件把 PR147 判成“无行为变化、可直接 approve”。这个判断不成立，至少有两点需要修正：

1. 插件默认模式从 `advise` 改成 `ask`，这是实际行为变化，不是单纯 additive
2. 长答案截断问题会直接影响这条 PR 新引入的 async wait 场景

因此这版 review 不建议直接批准合并。

---

## 正向评价

- `/v2/advisor/health` 把 mock LLM 暴露成 `degraded` 是正确方向
- `job_creation_failed` 不再把 traceback 直接回给调用方，这一点是实际改进
- Feishu WS 把 trace/context 补齐后，排障可观测性确实比之前好

---

## 建议结论

**先修 1 和 2，再合。**  
第 3 点可以和 1/2 一起修，也可以作为同 PR 的顺手收口项。
