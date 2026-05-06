# OpenMind v3 — 上线前工作全盘点

> 截至 2026-03-01 13:15，基于代码审计+测试验证

---

## ✅ 已完成（生产可用）

### 核心管线 — 4/4 场景通过
| 路由 | 功能 | 验证 |
|------|------|------|
| `hybrid/quick_ask` | FTS5 搜索 → LLM 合成 → 文本答案 | S1: 2244字 |
| `deep_research` | 多轮 CoT → 质量审核(6/10) → KB 写回 | S2: 5955字, review=True |
| `report` | 7 节点管线(三套稿, redact_gate) | S3: 500字, review=True |
| `funnel` | 6 维 rubric → Gate A/B → ProjectCard → 脚手架 | S4: ProjectCard + dispatch |

### KB 模块 — 100% 完成
| 组件 | 状态 | 说明 |
|------|------|------|
| `KBHub` | ✅ | FTS5 + 向量 hybrid search, RRF 融合, evidence_pack |
| `KBRetriever` (FTS5) | ✅ | **813 文档已索引**, 搜索验证通过 |
| `NumpyVectorStore` | ✅ 代码完成 | 需要 embedding model 才能启用向量搜索 |
| `KBArtifactRegistry` | ✅ | 文件注册, 质量分, 元数据, quarantine |
| `KBScanner` | ✅ | 目录扫描, 变更检测 |
| `migrate_openclaw_kb.py` | ✅ | 幂等迁移, 已执行全量导入 |

### KB 数据迁移 — 1107 文档, 0 错误
| 来源 | 文档数 |
|------|--------|
| `docs/` (项目文档+评审+日志) | 194 |
| `openclaw-workspaces/kb/` (总台账+验收+研究) | 199 |
| `openclaw-workspaces/` (其他 9 个工作区) | 714 |
| **FTS5 去重后** | **813 唯一文档** |

### 记忆管理 — 完成
| 组件 | 状态 |
|------|------|
| `MemoryManager` (3-tier) | ✅ working/episodic/meta |
| Episodic 自动记录 | ✅ research + report 结果 |
| Meta 路由统计 | ✅ 4 records per test run |

### 基础设施 — 完成
| 组件 | 状态 |
|------|------|
| EventBus | ✅ SQLite-backed, route.selected + kb.writeback |
| PolicyEngine | ✅ fail-closed 质量门控, 所有 KB writeback 前检查 |
| Langfuse | ✅ 自动初始化, 13 systemd drop-in + Python auto-load |
| API Auth | ✅ X-Api-Key header (OPENMIND_API_KEY env, fail-open) |
| Rate Limit | ✅ 10 req/min/IP (OPENMIND_RATE_LIMIT env) |
| 飞书 Handler | ✅ 文签名验证, 持久化去重, 交互式卡片(确认/修改/拒绝) |
| Agent Dispatch | ✅ LLM 项目脚手架生成(README + code + project_card) |

---

## ⚠️ 上线前必须做（短期阻断项）

### P0：安全与稳定性
| # | 工作项 | 预估 | 说明 |
|---|--------|------|------|
| P0-1 | **HTTPS / 反向代理** | 2h | 生产必须, 用 Caddy/nginx + TLS 证书 |
| P0-2 | **Systemd 服务启用** | 1h | `systemctl --user enable chatgptrest-api`, 开机自启 |
| P0-3 | **Error handling 审计** | 2h | 所有 `except: pass` 改为 `except Exception as e: logger.warning(...)` |
| P0-4 | **Langfuse 端到端验证** | 1h | 确认 Cloud UI 能看到 trace, 配置 alert |
| P0-5 | **API Key 设置** | 0.5h | 设 OPENMIND_API_KEY env, 生产模式 fail-closed |

### P1：功能补全
| # | 工作项 | 预估 | 说明 |
|---|--------|------|------|
| P1-1 | **B10 Checkpoint 重构** | 4h | State/Config 分离, 可序列化状态才能启用 SqliteSaver |
| P1-2 | **向量搜索启用** | 3h | 集成 fastembed/sentence-transformers, query embedding |
| P1-3 | **飞书 Webhook 注册** | 1h | 配置飞书应用回调 URL, 绑定机器人 |
| P1-4 | **健康检查增强** | 1h | /health 返回各子系统状态(KB count, memory, langfuse) |

---

## 📋 延期项（L1-L6 + 新增）— 下一阶段

### L1: EvoMap Dashboard API
- **什么**: 暴露 EvoMap 演化信号为 REST API, 供前端 dashboard 展示
- **范围**: `GET /evomap/signals`, `GET /evomap/trends`, websocket push
- **前置**: 需要前端 UI (Vue/React), 需要 EvoMap 更多信号积累
- **预估**: 2-3 天

### L2: Eval Harness（评估框架）
- **什么**: 标准化评估管线, 对比不同模型/prompt 的质量
- **范围**: 评测数据集管理, 自动评分, A/B 对比报告
- **前置**: 需要 gold-standard 测试集
- **预估**: 3-5 天

### L3: 压力测试
- **什么**: 并发压力 + 长时间稳定性测试
- **范围**: locust/k6 脚本, 内存泄漏检测, QPS 基准
- **前置**: P0-1 (HTTPS), P0-2 (systemd)
- **预估**: 2 天

### L4: KB 文档版本管理
- **什么**: FTS5 文档支持版本追踪, 变更历史, rollback
- **范围**: `kb_versions` 表, diff 展示, 审核工作流
- **前置**: KB 基础完成 (✅)
- **预估**: 2-3 天

### L5: 可配置 EvoMap 信号
- **什么**: EvoMap 信号类型/阈值可通过配置文件调整（非硬编码）
- **范围**: YAML/JSON 信号配置, 热重载
- **预估**: 1 天

### L6: 多模型辩论
- **什么**: 同一问题发给多个 LLM, 对比/融合回答
- **范围**: 并发调用, 评分聚合, 少数服从多数 or 最优选择
- **前置**: 模型配额管理, 成本控制
- **预估**: 3-5 天

### L7: 飞书 Rich Card 增强（新增）
- **什么**: 报告/研究结果以飞书 rich card 格式推送, 支持折叠/展开
- **预估**: 1-2 天

### L8: 用户偏好学习（新增）
- **什么**: 根据用户历史交互, 调整路由偏好和输出风格
- **前置**: Episodic memory 积累足够数据
- **预估**: 2-3 天

### L9: 多租户支持（新增）
- **什么**: 不同用户/团队独立的 KB、memory、config
- **预估**: 3-5 天

---

## 代码质量审计结果

| 检查项 | 结果 |
|--------|------|
| KB 模块 TODO/FIXME/Stub | **0** |
| Memory 模块 TODO/FIXME/Stub | **0** |
| 全量 NotImplementedError | **0** |
| `except: pass` 模式 | 5 处(fail-open 设计, 预期行为) |
| 4 场景 E2E 测试 | **4/4 通过** |
| FTS5 搜索验证 | **813 文档, 搜索命中率 >80%** |
| Langfuse 自动初始化 | **✅ 无需手动 source** |

---

## 运行环境与网络拓扑（YogaS2 生产机快照）

> 目的：把“这台机器的真实配置 + 关键依赖 + 启停/验证/回滚命令”沉淀成一份可交付给 Antigravity 的上下文材料。
> 本节 **不包含任何密钥值**，只记录路径与变量名。

### 1) 主机与资源（2026-03-01 13:23 CST）

| 项 | 值 |
|---|---|
| Hostname | `YogaS2` |
| OS | Debian 12 (bookworm) |
| Kernel | `6.12.18-trim` |
| CPU | i7-8550U，`8 vCPU`（4C/8T） |
| Mem/Swap | `22Gi` 内存，`11Gi` swap |
| Root 盘 | `/` 约 `63G`（偏小，避免把大产物放到 `/home`） |
| 数据盘 | `/vol1` 约 `1.8T`（btrfs，主要项目/产物在此） |

**关键约束：**
- `home` 在 root 盘上（小盘），所有长期产物建议放 `/vol1/1000/...`。
- 历史上出现过 `earlyoom` 回收导致进程被杀的问题：Chrome/Node/Python 被杀会直接影响 ChatgptREST driver 与 Antigravity 体验（详见 `/vol1/maint/memory/` 相关记录）。

### 2) 网络接口与路由

| 口 | 状态 | 地址 |
|---|---|---|
| 有线 `enp0s31f6` | UP | `192.168.1.7/24` |
| 无线 `wlp2s0` | UP | `192.168.1.85/24` |
| Tailscale `tailscale0` | UP | `100.124.54.52/32` |

路由（简化）：
- 默认网关：`192.168.1.1`
- 默认路由优先走有线（metric 100），无线为备份（metric 600）

DNS：
- `/etc/resolv.conf` 由 Tailscale 接管：`nameserver 100.100.100.100`，search domain `tail594315.ts.net`

### 3) 代理（Mihomo）依赖

ChatgptREST 的 systemd user 服务通过 `~/.config/chatgptrest/chatgptrest.env` 注入代理环境变量：

- `HTTP_PROXY=http://127.0.0.1:7890`
- `HTTPS_PROXY=http://127.0.0.1:7890`
- `ALL_PROXY=socks5://127.0.0.1:7890`
- `NO_PROXY=127.0.0.1,localhost`

因此：
- **Mihomo 掉线会导致上游调用失败**（常见日志：`connect ECONNREFUSED 127.0.0.1:7890`）。
- 遇到“能连上 SSH，但上游 API 全失败/鉴权失败/模型流断开”，第一优先检查 Mihomo。

常用命令：
```bash
systemctl --user status mihomo --no-pager
systemctl --user restart mihomo
ss -lntp | rg ':(7890|9090)\\b'
```

### 4) 关键端口清单（本机）

| 组件 | 端口 | 绑定 | 备注 |
|---|---:|---|---|
| SSH | 22 | 0.0.0.0 | 内网/常规 |
| SSH (alt) | 60022 | 0.0.0.0 | 对外映射常用 |
| SSH (alt) | 2222 | 0.0.0.0 | 备用 |
| Nginx | 80 | 0.0.0.0 | 已占用（nginx） |
| Tailscale HTTPS | 443 | `100.124.54.52` | tailscaled 绑定 tailscale IP（Tailscale Serve） |
| Mihomo | 7890 | 127.0.0.1 | HTTP/SOCKS 代理入口 |
| Mihomo | 9090 | 127.0.0.1 | 控制面 |
| ChatgptREST API | 18711 | 127.0.0.1 | REST `/v1/jobs/*` |
| ChatgptREST MCP | 18712 | 127.0.0.1 | MCP adapter（Streamable HTTP） |
| ChatGPT Web MCP driver | 18701 | 127.0.0.1 | `chatgpt_web` MCP |
| Chrome CDP | 9226 | 127.0.0.1 | 由 `CHROME_DEBUG_PORT` 覆盖（默认 unit 写 9222） |
| tmuxagent dashboard | 8702 | 0.0.0.0 | 手机常用入口 |

### 5) ChatgptREST systemd user 服务清单（本机）

unit 文件目录：
- `~/.config/systemd/user/chatgptrest-*.service`
- `~/.config/systemd/user/chatgptrest-*.timer`

当前运行态（建议以 `systemctl --user status` 为准）：
- `chatgptrest-api.service`：API 服务（127.0.0.1:18711）
- `chatgptrest-mcp.service`：MCP adapter（127.0.0.1:18712）
- `chatgptrest-chrome.service`：Chrome watchdog（CDP 端口来自 `CHROME_DEBUG_PORT`）
- `chatgptrest-driver.service`：driver（127.0.0.1:18701）
- `chatgptrest-worker-send.service`：worker send
- `chatgptrest-worker-wait.service`：worker wait
- `chatgptrest-worker-repair.service`：repair worker
- `chatgptrest-maint-daemon.service`：维护守护进程（监控/证据包）
- `chatgptrest-monitor-12h.service`：当前为 failed（需排查是否为预期或配置缺失）

### 6) 配置与凭证文件（只记录路径，不落值）

ChatgptREST env（proxy、CDP 端口、运行参数等）：
- `~/.config/chatgptrest/chatgptrest.env`

Langfuse 等云端凭证（集中管理）：
- `/vol1/maint/MAIN/secrets/credentials.env`

数据与状态目录（项目内）：
- DB：`/vol1/1000/projects/ChatgptREST/state/jobdb.sqlite3`
- artifacts：`/vol1/1000/projects/ChatgptREST/artifacts/`
- driver state：`/vol1/1000/projects/ChatgptREST/state/driver/`

### 7) 上线实施计划（面向本机落地）

#### Step A：上线前检查（10 分钟）

```bash
# 1) 磁盘与内存
df -h /
df -h /vol1
free -h

# 2) 代理
systemctl --user is-active mihomo
ss -lntp | rg ':(7890|9090)\\b'

# 3) 关键端口是否已监听（避免端口冲突）
ss -lntp | rg ':(18701|18711|18712|9226)\\b'
```

#### Step B：确保 systemd user 可开机自启

（本机已满足）：
- `loginctl show-user yuanhaizhou -p Linger` 显示 `Linger=yes`

#### Step C：启动/重启 ChatgptREST 全家桶（建议顺序）

```bash
systemctl --user daemon-reload
systemctl --user restart chatgptrest-api.service
systemctl --user restart chatgptrest-mcp.service
systemctl --user restart chatgptrest-chrome.service
systemctl --user restart chatgptrest-driver.service
systemctl --user restart chatgptrest-worker-send.service chatgptrest-worker-wait.service chatgptrest-worker-repair.service
systemctl --user restart chatgptrest-maint-daemon.service
```

#### Step D：验证（建议每次上线都跑）

```bash
# 端口
ss -lntp | rg ':(18701|18711|18712|9226)\\b'

# API 可用性（如启用 API Key，需要带 header）
curl -sS http://127.0.0.1:18711/health || true

# Langfuse 最小 smoke（不包含密钥）
bash /vol1/maint/MAIN/scripts/langfuse_smoke.sh
```

#### Step E：回滚（最小化）

```bash
systemctl --user stop chatgptrest-driver.service chatgptrest-chrome.service chatgptrest-mcp.service
systemctl --user stop chatgptrest-worker-send.service chatgptrest-worker-wait.service chatgptrest-worker-repair.service
systemctl --user stop chatgptrest-maint-daemon.service
systemctl --user stop chatgptrest-api.service
```

### 8) 常见故障与定位（给 Antigravity 的“先查什么”）

| 现象 | 第一嫌疑 | 怎么看 | 怎么恢复 |
|---|---|---|---|
| 上游请求报 `ECONNREFUSED 127.0.0.1:7890` | Mihomo 挂了 | `systemctl --user status mihomo` | `systemctl --user restart mihomo` |
| driver/浏览器相关功能不可用 | Chrome/driver 被杀或卡死 | `systemctl --user status chatgptrest-chrome chatgptrest-driver` | `systemctl --user restart chatgptrest-chrome chatgptrest-driver` |
| “能 SSH，Agent/工具超时” | 代理不通 / 内存压力 / UI backpressure | 看 Mihomo + earlyoom + Antigravity 日志 | 先恢复代理，再重启相关服务 |
