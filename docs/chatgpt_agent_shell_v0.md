# ChatGPTAgent 外壳层 v0（agent-mode）实现说明

> 目标：在保持 ChatgptREST REST 契约不变的前提下，给 `chatgpt_web.ask` 衍生一层“守护协议”外壳：
> - 多轮跟随（needs_followup）
> - 状态化会话管理
> - 缓存与幂等复用
> - 可控重试/回滚

## 一、实现文件与入口

- 实现脚本：`ops/chatgpt_agent_shell_v0.py`
- 会话状态目录：`state/chatgpt_agent_shell_v0/sessions/<session_id>.json`
- 回滚快照：`state/chatgpt_agent_shell_v0/sessions/<session_id>.bak`

## 二、接口（接口契约）

该外壳层通过本地 CLI 作为最小编排入口，底层仍只调用现有 API：

- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}/wait`
- `GET /v1/jobs/{job_id}/answer`

### 输入参数（CLI）

- `--question`：本轮用户问题（必填，非空）
- `--session-id`：会话标识（可复用）
- `--preset`：透传到 `params.preset`（默认 `auto`）
- `--agent-mode [on|off|auto]`：是否透传 `agent_mode=true`（默认 `on`）
- `--max-turns`：会话内最大轮次（默认 `3`）
- `--max-retries`：对 `blocked/cooldown/in_progress` 的重试上限（默认 `2`）
- `--retry-base-seconds` / `--retry-max-seconds`：退避配置
- `--timeout-seconds`/`--send-timeout-seconds`/`--wait-timeout-seconds`/`--max-wait-seconds`：透传参数
- `--min-chars`：用于 answer 长度阈值（默认 `800`）
- `--dry-run`：仅模拟流程，不发请求
- `--status`：只读会话状态
- `--rollback`：从 `.bak` 回滚会话（用于灰度异常回收）

### 输出字段（单次 ask 结果）

返回 JSON（或默认标准 JSON）主要字段：

- `ok`: bool
- `session_id`: 会话ID
- `status`: completed|error/canceled/blocked/cooldown/needs_followup/failed
- `job_id`, `conversation_url`, `answer`（completed）
- `round`: 当前轮次（自动 follow-up 轮次）
- `retries`: 本次调用累计重试次数
- `enabled`: 外壳层开关是否开启

### 响应行为

- 命中同问缓存（同一问题+会话会话标识+agent_mode+preset）直接返回 `mode=cache_hit`
- 无法完成或重试耗尽返回 `ok:false` 并携带 `error`

## 三、状态机（会话级）

### 外壳层状态（`state.chatgpt_agent_shell_v0`）

```text
idle -> submitting -> waiting ->
  |             |           |
  |             |           ├─ completed -> done
  |             |           ├─ error/canceled -> failed
  |             |           ├─ blocked/cooldown/in_progress -> cooldown / retry loop
  |             |           └─ needs_followup -> followup -> submitting
  |
  └─ failed / done -> submitting (新问题重试)
```

说明：

- `cooldown` 仅用于“外层退避等待后重新查询同一 job”；
- `needs_followup` 进入 followup 后，自动提交一次 follow-up（默认提示词），并继承 `parent_job_id`。

## 四、缓存与幂等（Cache / Idempotency）

### 缓存层

- **轮次缓存**：`turn_cache[question_fingerprint] -> {turn, job_id, status, conversation_url, answer}`
- **会话日志**：`turns` 保存最近 50 条转移记录
- **长度限制**：`turn_cache` 大小 > 200 时按更新时间裁剪

### 幂等层

- 每轮生成 idempotency key：
  - `agent-v0:<sha256(session_id|turn|preset|question|parent_job_id)>`
- 提交请求时放入 header `Idempotency-Key`
- 对于相同问题且未禁用 force，若本地缓存显示 `completed` 可直接复用答案，不走 API

## 五、重试与退避

### 触发条件

- 受理状态为：`blocked` / `cooldown` / `in_progress`
- `max_retries` 内每次失败后触发等待，再次 `wait` 查询同一 job（**不重发消息**）

### 退避公式

`backoff = min(retry_max_seconds, retry_base_seconds * 2^(retry_count)) * jitter(0.85~1.15)`

- `in_progress` 先尝试短窗口再次 wait（等待一次）
- `cooldown/blocked` 结合接口返回的 `retry_after_seconds`，兼容缺失时 fallback 到退避值
- 超过重试上限直接 `ok:false + max_retries_exceeded`

## 六、灰度与回滚策略

### 灰度开关

- 环境变量：`CHATGPT_AGENT_V0_ENABLED`
  - 未设置默认为 `true`
  - 设置为 `0/false/no/off` 可关闭外壳层（脚本仍可保留现有流程）

### 回滚策略

- **自动回滚**：`ask` 失败时默认会尝试恢复最近一次 `.bak` 会话快照（可用 `--no-roll-back` 禁用）
- **手动回滚**：`--rollback --session-id <id>` 强制从 `.bak` 恢复会话
- **快速降级**：关闭开关即可让调用方走传统单轮链路（不使用外壳层）

### 观测建议

- 将 `status`/`result` 落入当前监控（如 `run_monitor_12h.sh`）中作为指标源；观察字段：
  - `cooldown`, `needs_followup`, `failed`, `max_retries_exceeded`, `auto_followup_rounds`
- 连续异常建议先回滚外壳层（`CHATGPT_AGENT_V0_ENABLED=0`）后再看底层 job 健康。

## 七、最小联调脚本（一次运行）

```bash
# 1) 状态读取
python3 ops/chatgpt_agent_shell_v0.py --status --session-id demo --json

# 2) 提交一轮问题（agent mode）
python3 ops/chatgpt_agent_shell_v0.py \
  --session-id demo \
  --question "请给出本项目一次最小 API 巡检清单。" \
  --preset auto \
  --max-turns 3 \
  --max-retries 2 \
  --json

# 3) 回滚上一次会话（异常后）
python3 ops/chatgpt_agent_shell_v0.py --session-id demo --rollback
```

> 该脚本不新增/替换 REST 契约；仅提供“guardian 式”外壳层，所有底层动作仍在已有 `/v1/jobs*` 套件中完成。
