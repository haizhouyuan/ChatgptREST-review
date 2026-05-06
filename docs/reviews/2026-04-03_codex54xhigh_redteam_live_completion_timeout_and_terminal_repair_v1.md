# 2026-04-03 Codex54xhigh Redteam Live Completion Timeout And Terminal Repair v1

## Redteam verdict

Verdict: `approve-with-scope-tightening`.

红队没有反对这批的主方向，但明确反对把未被 live 证据坐实的 public-surface 语义改动和 gate truthfulness 改动混在同一个 mouthpiece 里提交。

## 我采纳的意见

### 1. 撤出 `target crashed/closed -> same_session_repair` 这条 public-surface 改动

红队指出：

- 这会把原本更接近 infra recovery 的 `cooldown + browser crash` 提前投影成 public `needs_followup/clarify_required`
- 当前批次没有 live 证据证明这条新语义已经正确

我接受这个批评，所以最终提交范围里：

- 不包含 `routes_agent_v3.py` 的这条扩张
- 不包含对应的 mocked session-alignment 测试

### 2. 收紧 review/master plan 口径

红队指出：

- `v5` 只能证明一个 live `needs_followup` 终态、task/checkpoint 对齐、以及 non-green actionable repair
- 不能把它说成三态全部证明，更不能说成最终 provider root cause 已冻结

我接受这个批评，所以最终文档口径只保留：

- `probe_failed` 的 truthful fail-closed
- `needs_followup` 的 truthful non-green terminal observation
- `final completion / answer quality` 仍未过线

## 我没有采纳的部分

没有未采纳的 blocker。当前红队的关键点都已经吸收进提交范围与文档口径。

## 当前允许提交的范围

红队收紧后，我认为这批允许提交的范围是：

- live completion gate timeout hardening
- runner 的 non-green exit semantics
- `v4/v5` 两份 live evidence 对应的 truthfulness 文档冻结

而不是：

- 任何新的 public-surface repair 语义扩张
- 任何“已经 live 做绿”的说法
