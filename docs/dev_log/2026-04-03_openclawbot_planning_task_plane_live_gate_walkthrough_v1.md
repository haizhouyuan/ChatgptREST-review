# 2026-04-03 OpenClawBot Planning Task Plane Live Gate Walkthrough v1

## 1. 为什么这一步必须做

到 `v17` 为止，我们已经有：

1. `OpenClawBot` 主链 acceptance
2. owner guard
3. continue 收紧
4. single-host multiprocess lock

但还差一层很关键的现实检验：

> 这些东西在真实 provider / 真实 integrated host 上，是不是还能成立。

如果不做这层 live gate，前面的很多“可用”结论都只停在：

1. TestClient
2. mocked controller
3. repo-internal proof

## 2. 我先发现了什么

### 2.1 不能直打 `/v3/agent/turn`

我先做了一个最直接的 live probe：

1. 带 API key
2. 直接 POST `/v3/agent/turn`

结果被 `403 client_not_allowed` 拦住。

这说明：

1. live gate 必须走 allowlisted client
2. 不能用“我本机脚本能打 API”冒充真实 northbound

### 2.2 live host 没加载到最新代码

接着我又发现：

1. live `/v3/agent/session/{id}` 在
2. 但 `/v3/agent/planning/tasks` 还是 `404`

这不是代码没写，而是服务进程还停在旧版本。

所以中途先做了：

1. `systemctl --user restart chatgptrest-api.service`

重启后 planning route 才真的挂出来。

## 3. live gate 是怎么做的

我没有再造一套新入口，而是直接复用了现有 OpenClaw plugin helper：

1. `_execute_openclaw_plugin_tool(...)`
2. `x-client-name=openclaw-advisor`
3. real `18711`

然后把 gate 拆成 4 个 live 检查：

1. `openclaw_live_ask_observable`
2. `planning_task_list_visible`
3. `planning_task_get_visible`
4. `live_session_observable`

这 4 个检查故意不要求：

1. 最终一定 `completed`
2. 回答质量一定达标

因为真实 provider 下第一跳可能就是：

1. `running`
2. `needs_followup`
3. `completed`

我们这一步要证明的是：

1. continuity 还活着
2. session/task 都还看得见

## 4. live 实测给出的新认识

这次 live run 最值钱的不是通过本身，而是它暴露出的真实 lifecycle：

1. `route=funnel`
2. `final_provider=chatgpt`
3. `session_status=needs_followup`
4. `next_action_type=same_session_repair`

这说明：

1. planning task plane 和 live provider 是接上的
2. 但“第一跳同步完成”不是应该默认相信的事

换句话说，下一批 live acceptance 不能再只看：

1. 有没有 answer

而要看：

1. lifecycle 怎么流转
2. repair/followup 怎么收口

## 5. 这一轮之后，计划怎么改

我现在对后续的判断更清楚了：

1. continuity proof 已经跨过 live host 这道坎
2. 下一批最值得投的是 final-completion / answer-quality live acceptance
3. 而不是继续在 continuity sidecar 上小修小补

所以这一步不是又加了一个 eval 脚本，而是把“下一批真正该攻什么”也钉死了。
