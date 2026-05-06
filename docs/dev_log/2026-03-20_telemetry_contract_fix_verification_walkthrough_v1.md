# 2026-03-20 Telemetry Contract Fix Verification Walkthrough v1

## 1. 任务目标

核验 [2026-03-20_telemetry_contract_fix_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_telemetry_contract_fix_v1.md) 是否已经把 telemetry 线的 contract 和 live drift 收清，并判断它能否作为当前 freeze。

## 2. 这次核验重点

这次我重点复核了 5 件事：

1. `/v2/telemetry/ingest` 是否仍然挂在 FastAPI cognitive router
2. telemetry canonical 是否已经被正确从 HTTP route 拆回 `EventBus / observer / signals`
3. OpenClaw 四个 OpenMind 插件 live target 是否确实都是 `18711`
4. `18713 404` 是否真的来自 GitNexus Node/Express
5. `/v3/agent/*` facade session telemetry 是否仍未桥进 canonical plane

## 3. 重新核对的对象

- [routes_cognitive.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_cognitive.py#L311)
- [app.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/app.py#L150)
- [telemetry_service.py](/vol1/1000/projects/ChatgptREST/chatgptrest/cognitive/telemetry_service.py#L62)
- [event_bus.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/event_bus.py#L151)
- [runtime.py](/vol1/1000/projects/ChatgptREST/chatgptrest/advisor/runtime.py#L203)
- [routes_agent_v3.py](/vol1/1000/projects/ChatgptREST/chatgptrest/api/routes_agent_v3.py#L968)
- [openmind-telemetry/index.ts](/vol1/1000/projects/ChatgptREST/openclaw_extensions/openmind-telemetry/index.ts#L50)
- [/vol1/maint/ops/scripts/agent_activity_event.py](/vol1/maint/ops/scripts/agent_activity_event.py#L27)
- [openclaw.json](/home/yuanhaizhou/.home-codex-official/.openclaw/openclaw.json#L165)
- `systemctl --user status chatgptrest-api.service openclaw-gateway.service`
- `ss -ltnp`
- `ps -fp 2939905`
- `curl -X POST http://127.0.0.1:18713/v2/telemetry/ingest`

## 4. 这次确认成立的部分

我确认 `v1` 这次把 telemetry 线真正拆清了：

- canonical telemetry plane 不是单一 HTTP route
- canonical HTTP ingest seam 仍然是 FastAPI 上的 `POST /v2/telemetry/ingest`
- OpenClaw 四个 OpenMind 插件当前 live config 都还指向 `http://127.0.0.1:18711`
- 当前 `18713` 确实是 GitNexus 的 Node/Express 服务
- `/v3/agent/*` facade session telemetry 还没有桥进 canonical plane，这条 gap 也被如实保留了

## 5. 这次没有发现什么问题

这次没有发现需要继续升级到 `v2` 的实质性问题。

原因是：

- route ownership 有直接代码证据
- canonical plane 有直接 runtime/in-process emitter 证据
- live target 有 openclaw.json 安装态证据
- `18713` 的服务身份和返回头都已被 live 进程与 curl 坐实
- facade gap 经过 repo 搜索没有发现隐含桥接

## 6. 边界说明

这轮唯一要保留的边界不是 finding，而是表述边界：

- `18713 = GitNexus serve` 是当前 live drift 事实，不是抽象 contract
- 抽象 contract 仍应优先写 “FastAPI cognitive ingress”
- 但在当前 live host 上，把 `18713 fallback` 定性为过时假设是准确的

## 7. 最终判断

所以这轮核验的最终判断是：

- `telemetry_contract_fix_v1` 已经足够稳
- 可以作为 telemetry contract 这一线的当前 freeze
- 下一步直接进入 mirror fallback 清理、API 恢复、facade telemetry bridge 三个实现面是合理的

## 8. 产物

本轮新增：

- [2026-03-20_telemetry_contract_fix_verification_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_telemetry_contract_fix_verification_v1.md)
- [2026-03-20_telemetry_contract_fix_verification_walkthrough_v1.md](/vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-20_telemetry_contract_fix_verification_walkthrough_v1.md)

## 9. 测试说明

这轮仍然只是文档与代码证据核验，没有改业务代码，没有跑测试。
