# 2026-04-03 Meeting Sedimentation Phase-1 Slice Execution Walkthrough v2

## 1. 为什么会有 v2

`v1` 已经把 continuity sidecar 接出来了，但第一次严格红队之后，暴露出两个关键尾巴：

1. 失败 checkpoint 没写真实异常文本
2. deferred 背景线程里，如果 checkpoint 写回自己抛错，session 仍可能卡在 `running`

所以 `v2` 的目标不是加新面，而是把异常尾巴补硬。

## 2. 这次怎么补的

### 2.1 先把失败尾巴收成一个 helper

在 [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py) 里新增了：

1. `_persist_agent_turn_failure(...)`

它统一负责：

1. checkpoint failed 写回
2. session failed 持久化
3. error event append
4. 完整写回失败后的最小 fallback session write

这样 sync / deferred 两条失败路径不再各自散写一段脆弱逻辑。

### 2.2 再把异常文本写进 checkpoint

之前 `_mark_meeting_task_failed(error_text=\"\")` 会让 task 文件里只有 `failed` 状态，没有失败原因。

现在改成：

1. 统一先生成 `error_text = str(exc)[:500]`
2. 再把这个 `error_text` 传进 checkpoint 写回
3. 同一份 `error_text` 继续用于 session error 和 HTTP 500 payload

这一步的价值很实际：

1. 以后人或 bot 回来看 task 文件，不用先跳去 session events 才知道为什么失败

### 2.3 用故障注入测护栏，而不是只测正常失败

这次新增的重点不是普通 failure case，而是：

1. `MeetingTaskStore.update_checkpoint` 在 `status=failed` 时主动抛错

然后分别验证：

1. deferred 路径下 session 仍会进 `failed`
2. sync 路径下 session 仍会进 `failed`
3. task 文件不会假装自己已经写成 `failed`

也就是说，这次不是在测“正常失败能不能失败”，而是在测“失败护栏自己炸了以后，系统还会不会继续收口”。

## 3. 红队怎么影响了这次实现

### 3.1 第一轮成功红队

成功红队先抓到了：

1. empty-materials miscontinuation
2. failure checkpoint 没有异常文本
3. deferred failure tail 没兜住 checkpoint writeback 自身异常

### 3.2 第二轮成功红队

第二轮继续收紧：

1. 只兜 checkpoint writeback 还不够
2. 后面的 session persistence / event append 也要考虑 failure tail

所以我把这一步最终实现收到了统一 helper，而不是继续在两条 except 里缝补。

### 3.3 最后一轮严格复核状态

我又发起了更窄的 `claudegac` strict review，目标是给 post-fix 最终 verdict。

现状是：

1. review 请求已发出
2. 但最后 run 因额度不足返回 `402 insufficient credits`
3. 所以这轮没有拿到新的最终 verdict 文本

这不是代码逻辑失败，而是外部审核资源失败。

## 4. 这一步之后，计划状态怎么变

现在 phase-1 已经可以更准确地说成：

1. continuity sidecar 已接入
2. 常见 failure persistence 已补到 phase-1 可用
3. 下一步不该回头重复争论这条切片是否存在，而应该继续做：
   - OpenClawBot 侧 continue / retrieve 使用面
   - 或者下一条 planning 任务类型切片

## 5. 本次最重要的经验

这次最有价值的经验不是“多写了一个 helper”，而是：

1. 任务 continuity 不能只测 happy path
2. 失败护栏必须接受故障注入
3. 红队真正值钱的地方，是把“看起来已经兜住”继续往下掰到“失败尾巴本身还会不会再炸”
