# 2026-03-15 Maintagent Bootstrap Memory Injection v1

## Why

`maint_daemon` 和 `sre.fix_request` 之前只有两类记忆：

- incident / issue / target job 的局部上下文
- `codex_global_memory` 里的故障模式与动作摘要

它们缺少机器和工作区的长期事实，所以 maintagent 在诊断时并不知道：

- 当前机器已经是约 `32GB` 内存，而不是旧文档里的 `24GB`
- `/etc/resolv.conf` 当前是自定义 DNS，不是旧文档描述的 Tailscale 管理
- 根分区已到 `85%`
- 当前 repo/worktree 总数已经扩到 `73`
- `ChatgptREST / homeagent / codexread` 是当前三大家族

这些事实已经被整理到 `/vol1/maint` 的 memory packet，但还没有注入到 ChatgptREST 的 repair/maint prompts。

## What Changed

### Shared bootstrap memory loader

新增 [maint_memory.py](/vol1/1000/projects/ChatgptREST/.worktrees/maint-self-heal-full-20260315/chatgptrest/ops_shared/maint_memory.py)：

- 自动发现 `/vol1/maint/exports/maintagent_memory_packet_*.json`
- 支持 `CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_PACKET` 显式覆盖
- 支持 `CHATGPTREST_MAINT_BOOTSTRAP_MEMORY_STALE_HOURS` 标记 stale packet
- 把 packet 渲染成 prompt-safe 的 `Maintagent Bootstrap Memory` 段
- 能把 bootstrap 段合并进 `codex_global_memory.md`

### Maint daemon memory path

修改 [maint_daemon.py](/vol1/1000/projects/ChatgptREST/.worktrees/maint-self-heal-full-20260315/ops/maint_daemon.py) 和 [ops/_maint_codex_memory.py](/vol1/1000/projects/ChatgptREST/.worktrees/maint-self-heal-full-20260315/ops/_maint_codex_memory.py)：

- `codex_global_memory.md` 现在除了故障模式，还会带上 bootstrap memory
- 即使还没有任何 incident-pattern digest，只要 packet 存在，incident snapshot 也会生成 bootstrap-only memory 文件
- 缺失 packet 时保持旧行为，不阻塞 maint daemon

### SRE lane memory

修改 [sre.py](/vol1/1000/projects/ChatgptREST/.worktrees/maint-self-heal-full-20260315/chatgptrest/executors/sre.py)：

- `sre.fix_request` prompt 现在会附带 `Maintagent bootstrap memory`
- lane request artifact 会记录 bootstrap source / freshness metadata

## Verification

通过的测试：

- `tests/test_maint_bootstrap_memory.py`
- `tests/test_sre_fix_request.py`

验证点：

- packet 可被正确解析为 prompt-safe memory
- bootstrap memory 只插入一次，不重复污染 markdown
- 在 `codex_global_memory.md` 尚不存在时，maint daemon 仍可生成 bootstrap snapshot
- `sre.fix_request` 的 prompt 确实包含 repo/worktree 与 drift 事实

## Operational Notes

- 推荐把 `/vol1/maint/docs/2026-03-15_maintagent_memory_index.md`、两份 snapshot、以及 packet JSON 继续作为外部权威来源维护，不要把整份 docs 拷进 ChatgptREST。
- ChatgptREST 只消费压缩后的 bootstrap memory，不复制 secrets，也不把整份外部快照长时间写入本仓状态机。
- 如果后续 `/vol1/maint` 改成新的 packet 命名，只需要继续满足 `maintagent_memory_packet_*.json` 或显式配置环境变量。
