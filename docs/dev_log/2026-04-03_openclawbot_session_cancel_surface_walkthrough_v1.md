# 2026-04-03 OpenClawBot Session Cancel Surface Walkthrough v1

## 做了什么

1. 给 `openmind-advisor` plugin 增加了 `openmind_advisor_session_cancel`。
2. 让 session 摘要 payload 保留 `message` / `cancelled_job_ids`。
3. 把 `session_cancel` 纳入 offline acceptance pack。
4. 补了 plugin/source 断言和 acceptance scope 断言。
5. 回归了后端 `/v3/agent/cancel` 的代表性测试。

## 为什么做

因为 phase-1 owner-path 之前只有：

- 能发起
- 能查询
- 能继续

但还没有：

- 能明确取消/收口

这会让 OpenClawBot 侧虽然能持有任务线程，却缺少最基本的 owner control。

## 这批故意不做什么

1. 不去碰 live dynamic replay 的根因。
2. 不新增 live cancel gate，避免在 live lane 未稳时继续放大变数。
3. 不把 planning task status 语义重新设计成“cancelled task plane”。
4. 不扩大 publicagentmcp 或 task_runtime 范围。

## 当前结果

owner-path 现在具备：

- ask
- session_get
- session_cancel

并且 acceptance pack 已经把“继续后可取消”纳入显式证据面。


## 红队状态

这批按既定策略发起了 `codex 5.4-xhigh` red-team review，但 subagent 在当前会话资源状态下未在可接受时间内返回 terminal verdict。

所以这批的收口依据是：

- 本地定向测试通过
- 后端 cancel 路由回归通过
- 我对 overclaim 风险做了收紧，不把这批写成“live cancel 已验证”

后续如果 redteam 能补回 verdict，再单独落修订版文档。