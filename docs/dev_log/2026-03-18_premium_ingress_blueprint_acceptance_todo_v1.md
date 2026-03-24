# Premium Ingress Blueprint Acceptance TODO v1

日期：2026-03-18

这是 Codex 对后续 `cc-sessiond` 实现任务的验收 TODO，不是给 Claude Code 的实现说明。

## 验收 TODO

1. 确认 branch/worktree 隔离干净，没有把主仓 pre-existing finbot 脏改动带进去。
2. 审核 `/v3/agent/turn` 是否真的先形成 ask contract，而不是继续直接吃自由文本。
3. 审核 legacy funnel 是否真正接到 ingress 前置层，而不是只在 advisor 内部遗留。
4. 审核服务端 prompt assembly 是否已经成形，且消费 contract/template。
5. 审核 post-ask review 是否每次 premium ask 都产生结构化结果。
6. 审核 review signal 是否写入 EvoMap 或等价持久层。
7. 审核 `advisor_agent_turn` / OpenClaw / CLI 是否仍兼容。
8. 审核普通 premium ask 没有误入 `cc-sessiond` slow path。
9. 跑实现者声称的测试命令并复核结果。
10. 追加 live-focused smoke：
   - `/v3/agent/turn`
   - `/v3/agent/session/{session_id}`
   - `/v3/agent/session/{session_id}/stream`
   - MCP tools/list 仍只暴露 agent 3 tools
11. 做 merge 前 scope check：
   - 关注 routes_agent_v3
   - prompt/contract/funnel modules
   - review/evomap writeback modules
   - OpenClaw compatibility files
12. 合并前确认新增文档都有版本号且未覆盖旧版。
13. 合并后重跑核心回归并重启 API/MCP。
14. 重启后做 live verification，再写 rollout walkthrough。
