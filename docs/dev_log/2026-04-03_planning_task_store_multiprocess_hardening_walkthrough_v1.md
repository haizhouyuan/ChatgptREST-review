# 2026-04-03 Planning Task Store Multiprocess Hardening Walkthrough v1

## 1. 为什么这一步必须继续做

到 `v16` 为止，planning task plane 的上层主链已经有 `OpenClawBot` evidence，但底层 store 还留着一个不能装看不见的问题：

1. 之前只靠 `threading.RLock()`
2. 这只能保证同进程线程安全
3. 对多进程完全不够

而我们的现实环境恰好就是：

1. OpenClawBot
2. API 进程
3. 测试 / acceptance harness
4. 以后可能还有别的 worker/process

所以如果这里不补，前面主链证据再漂亮，也可能在 runtime 上被竞争条件打穿。

## 2. 我怎么做的

### 2.1 先把锁边界想清楚

我没有把 `flock` 零散塞进某几个写方法，而是先统一成一个 `_guard()`：

1. 先拿进程内 `RLock`
2. 再拿 store 目录下 `.lock` 的 `fcntl.flock`
3. 然后把 `load/get/put/save` 和高层 `resolve/update/list/get_public` 都纳入这个 critical section

这样做的目的，是避免出现：

1. `resolve_task()` 用了 process lock
2. 但 `get_public()` 或 `put()` 没有
3. 最后还是留一半裸露面

### 2.2 再把 unlocked helpers 拆出来

为了避免 public method 之间相互调用时重复上锁，我把底层文件操作拆成：

1. `_load_index_unlocked`
2. `_save_index_unlocked`
3. `_get_unlocked`
4. `_put_unlocked`

public method 统一在 `_guard()` 内调 unlocked helpers。

### 2.3 顺手把 `set` 输入关掉

这是低成本但很值的补丁。

之前 `_normalize_text_list()` 接受 `set`，虽然不一定直接出错，但会带来：

1. 顺序不稳定
2. merge 结果不稳定
3. 断言不稳定

所以这次直接收成：

1. `list / tuple / str` 支持
2. 其它 malformed shape fail-closed

## 3. 我怎么证明它不是纸面安全

我没有只写一个“锁存在”的测试，而是写了两个真正跨进程的测试：

1. 两进程同时 `resolve_task()`
   - 看是否分裂出两个 task
2. 两进程同时 `update_checkpoint()`
   - 看是否丢一个 artifact merge

这两条测试比静态检查更重要，因为它们验证的是：

1. 多进程锁是否真的生效
2. 高层业务语义是否仍然成立

## 4. 这一步之后，怎么理解它的边界

我接受的结论是：

1. 本机多进程安全已经补上
2. 这足以把之前红队那句“只有 thread lock”改掉

但我没有把它说成：

1. 已经是最终 canonical runtime
2. 已经证明跨主机 durability
3. 已经证明 network filesystem 语义

所以这一步是 runtime hardening，不是把 phase-1 sidecar 直接升格。

## 5. 这一步的价值

现在 planning task plane 的状态，比 `v16` 又更实一点：

1. 上层有 `OpenClawBot` 主链 acceptance
2. 中层有 owner guard / continue 收紧
3. 底层有 single-host multiprocess lock

也就是说，当前这条线已经不是“概念验证”，而是在往真实可用的 runtime 面收口。
