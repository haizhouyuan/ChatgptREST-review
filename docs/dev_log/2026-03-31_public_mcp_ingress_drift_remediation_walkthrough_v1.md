# 2026-03-31 Public MCP Ingress Drift Remediation Walkthrough v1

## 背景

这次排查的现象不是服务宕机，而是“服务健康检查正常，但客户端体感不可用”。深入核对后，确认至少有两类真实问题叠在一起：

1. `Antigravity` 本地 `mcp_config.json` 仍在使用 legacy `serverURL`，不满足当前 public MCP 的 canonical HTTP 配置契约。
2. live `ops/chrome_watchdog.sh` 默认把 `/v1/issues/report` 指到了 `18712`，导致 issue API 被错发到 MCP 端口。

这说明问题不只是某个 agent 临时误用，而是“入口契约缺少统一漂移门禁”。服务本体健康，并不等于客户端接入面健康。

## 根因

根因收敛为两条：

1. **入口契约知识分散**
   `18711` 是 REST API，`18712/mcp` 是 public MCP，但这条边界主要出现在 runbook / README，agent 最先读取的入口文档没有把它提升成第一层护栏。

2. **漂移检查只看客户端，不看 runtime**
   仓内已有 `ops/check_public_mcp_client_configs.py`，但之前只覆盖已知客户端配置和 skill wrapper，没有把 live runtime 脚本也纳入同一个检查面，所以 `chrome_watchdog.sh` 的默认端口漂移没有被同一套门禁发现。

## 本次改动

### 1. 修复 live runtime 错配

- [ops/chrome_watchdog.sh](/vol1/1000/projects/ChatgptREST/ops/chrome_watchdog.sh)
  - 把 issue ledger 默认 API 端口从 `18712` 改成 `18711`
  - 加注释说明 issue API 属于 REST API，不属于 public MCP

### 2. 强化统一 ingress drift checker

- [ops/check_public_mcp_client_configs.py](/vol1/1000/projects/ChatgptREST/ops/check_public_mcp_client_configs.py)
  - 新增 `collect_alignment_report()`，让检查逻辑可被其他维护工具复用
  - `--fix` 现在可原地修复已知 `Antigravity` 配置漂移
  - 新增 `inspect_chrome_watchdog_contract()`，把 runtime 脚本也纳入同一份 drift 报告
  - 对 `Antigravity` 的 legacy `serverURL` 给出明确 reason：`legacy_serverURL_field`

### 3. 把 drift 检查接入健康探针

- [ops/health_probe.py](/vol1/1000/projects/ChatgptREST/ops/health_probe.py)
  - 新增 `public_mcp_ingress_contract` 检查项
  - health probe 不再只看“端口是否活着”，还会看：
    - 已登记 Codex / Claude / Antigravity 配置
    - skill wrapper
    - live `chrome_watchdog.sh`
  - 这样以后即使服务进程全绿，只要入口契约漂移，`health_probe` 也会 fail closed

### 4. 补强 agent 最先看到的入口护栏

- [AGENTS.md](/vol1/1000/projects/ChatgptREST/AGENTS.md)
- [docs/codex_fresh_client_quickstart.md](/vol1/1000/projects/ChatgptREST/docs/codex_fresh_client_quickstart.md)
- [docs/runbook.md](/vol1/1000/projects/ChatgptREST/docs/runbook.md)
- [README.md](/vol1/1000/projects/ChatgptREST/README.md)

新增的显式护栏包括：

- `18711` 只给 REST API
- `18712` 只给 public MCP，且必须写成 `http://127.0.0.1:18712/mcp`
- Claude Code / Antigravity JSON 配置必须写 `"type": "http"` + `"url": ...`，不要再用 `serverURL`
- 怀疑漂移时，优先跑 `python3 ops/check_public_mcp_client_configs.py --fix`

## 验证

### 代码与测试

执行的定向验证：

```bash
./.venv/bin/pytest -q tests/test_check_public_mcp_client_configs.py tests/test_health_probe.py
python3 ops/check_public_mcp_client_configs.py
python3 ops/check_public_mcp_client_configs.py --fix
python3 ops/check_public_mcp_client_configs.py
python3 ops/health_probe.py --json
bash -n ops/chrome_watchdog.sh
```

### live 修复

执行了：

```bash
systemctl --user restart chatgptrest-chrome.service
systemctl --user status chatgptrest-chrome.service --no-pager --lines=20
```

同时重新核对：

- `Antigravity` 配置已从 legacy `serverURL` 修正为 canonical `type=http + url=http://127.0.0.1:18712/mcp`
- `chrome_watchdog` 已加载新脚本版本
- `ops/check_public_mcp_client_configs.py` 返回全绿
- `ops/health_probe.py --json` 新增 `public_mcp_ingress_contract` 检查且为 `ok=true`

## 防复发结论

这次真正补上的，不只是一个端口值，而是：

1. **统一检查面**：客户端配置和 runtime 脚本不再各自漂、各自排查
2. **入口前移**：最先被 agent 读到的文档现在就写清端口/transport/config 约束
3. **健康探针收口**：以后“服务活着但入口漂了”的状态会直接出现在健康探针里，而不是靠日志猜

这条线的目标不是保证所有外部上游都永远不出问题，而是把“同类错配再次悄悄回流到 live”变成更难发生、更早暴露的事情。
