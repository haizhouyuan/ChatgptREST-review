# 2026-04-03 Planning Task Checkpoint Query CLI Walkthrough v1

## 本次做了什么

1. 检查 `W2` 当前缺口，确认已有脚本更偏“写回完成”，但缺少同样顺手的“读回 checkpoint / 列最近 task”入口
2. 新增两条薄 CLI：
   - `planning_task_checkpoint_get.py`
   - `planning_task_checkpoint_list.py`
3. 默认安全路径统一走 identity-gated public read/list，不再默认裸读 raw task record
4. 收紧 session fallback：默认不再接受 `TMUX_PANE / TERM_SESSION_ID` 这种隐式窗口身份
5. 保留 `--unsafe-local-read` 作为 maintenance-only 例外，并在测试与文档里显式标注
6. 补齐 targeted tests，并保留已有 `complete / writeback` 回归

## 为什么这一步有价值

之前跨端继续 planning task 时，系统已经有 task truth 数据，但使用上仍然偏原始：

1. 要么自己翻 JSON
2. 要么只会把结果写回，取不回来

这两个 CLI 把现有能力变成了更接近工作流的入口。

## 这次专门修掉的边界问题

1. `get` 默认绕过 identity 的风险已经消掉
2. `TMUX_PANE / TERM_SESSION_ID` 造成的 session-only 混淆面已经从默认行为中移除
3. `unsafe-local-read` 仍然存在，但被明确降级为维护尖锐工具，不算正常用户路径

## 当前边界

这一步仍然是薄 CLI，不是 task truth layer 的最终形态。下一步还应继续补：

1. 更稳定的 handoff contract
2. 更完整的 resume / branch 规则
3. OpenClawBot 与深度工作台之间更自然的接力
