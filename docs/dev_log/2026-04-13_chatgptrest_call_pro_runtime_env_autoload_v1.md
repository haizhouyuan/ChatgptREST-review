# 2026-04-13 ChatgptREST Call Pro Runtime Env Autoload v1

## Context

在维护场景里，`skills-src/chatgptrest-call/scripts/chatgptrest_call.py` 需要显式走：

- `--no-agent`
- `--maintenance-legacy-jobs`
- `--provider chatgpt`
- `--preset pro_extended`

用户这次明确要求“问 ChatGPT Pro，不是 Deep Research”。旧调用链里存在两个现实问题：

1. wrapper 没有自动加载 systemd live runtime 使用的 env 文件，导致 `chatgptrestctl-maint` 低层 ask 命中：
   - `HMAC secret env CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT is not configured`
2. legacy mode 通过 `python -m chatgptrest.cli` 子进程执行时，没有显式固定 repo root 作为 `cwd`，对维护 wrapper 来说不够稳。

## Change

### 1. runtime env autoload

在 wrapper 启动期新增了自动补环境逻辑：

- 优先读取 `~/.config/chatgptrest/chatgptrest.env`
- 兼容读取 `/vol1/maint/MAIN/secrets/credentials.env`
- 仅在当前 shell 缺失变量时才补齐，不覆盖现有 env
- 只记录“从哪个文件补了哪些 key”，不输出 secret 值

这让以下维护态变量默认可用：

- `CHATGPTREST_ASK_HMAC_SECRET_CTL_MAINT`
- `CHATGPTREST_API_TOKEN`
- `CHATGPTREST_OPS_TOKEN`

### 2. legacy CLI cwd hardening

`_run_json_command()` 现在显式以 ChatgptREST repo root 作为 `cwd` 执行子进程，避免维护 wrapper 对调用者当前工作目录产生脆弱依赖。

### 3. operator-facing docs/skill wording

同步澄清了：

- `ChatGPT Pro != Deep Research`
- “问 Pro” 应走 `provider=chatgpt + preset=pro_extended`
- 只有显式需要 Deep Research 时才应再加 `--deep-research`

## Validation

聚焦测试：

```bash
./.venv/bin/pytest -q tests/test_skill_chatgptrest_call.py tests/test_skill_chatgptrest_call_coding_agent_v1.py
```

通过。

新增/更新的覆盖点：

- runtime env autoload 能从标准 env 文件补齐变量
- legacy jobs mode 现在显式用 repo root 作为子进程 `cwd`
- coding-agent tests 与当前 surface 自动升级语义保持一致

## Files

- `skills-src/chatgptrest-call/scripts/chatgptrest_call.py`
- `skills-src/chatgptrest-call/SKILL.md`
- `README.md`
- `docs/runbook.md`
- `tests/test_skill_chatgptrest_call.py`
- `tests/test_skill_chatgptrest_call_coding_agent_v1.py`

## Operational note

这次修复的目标不是改变默认 northbound 路线。coding agent 仍然默认走 public MCP。

修复的是：

- 当维护者明确要求 legacy `ChatGPT Pro` ask 时
- wrapper 应该能自动继承 live runtime 的维护密钥与 token
- 并且不要再把 `Pro` 和 `Deep Research` 混为一谈
