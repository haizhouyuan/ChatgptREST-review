# ChatgptREST Direct REST Access And Research Runtime Findings

## 背景

为执行 `report_grade` 与 `deep_research` 研究任务，本次对本机 `ChatgptREST` 的 direct REST 与 runtime 行为做了一次 live 校正。

## 已修复问题

### 1. `chatgptrestctl-maint` runtime allowlist 漂移

代码、测试和文档都要求 direct `/v3/agent/*` 允许 `chatgptrestctl-maint`：

- `chatgptrest/api/routes_agent_v3.py`
- `tests/test_routes_agent_v3.py`
- `docs/dev_log/2026-03-23_public_agent_direct_rest_guard_v1.md`

但 live runtime 的 `CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST` 漏掉了该 client，导致 direct REST 调用被拒。

本次已在本机 runtime env 中补齐 `chatgptrestctl-maint`，并重启：

- `chatgptrest-api.service`

修复后，direct REST research session 可以成功进入：

- `conversation_url_set`
- `prompt_sent`
- `phase_changed: send -> wait`

## 本次新增观察

### 2. slash-like prompt token 会触发 `AttachmentContractMissing`

研究型 prompt 中如果包含下列类似 token：

- `LangGraph/LangMem`
- `retrieval/write`
- `episodic/semantic/procedural`

当前 server synthesize / attachment contract 可能将其误判为本地文件引用，进而触发 `AttachmentContractMissing`。

这说明：

1. 研究型 prompt 在进入 `advisor_agent_turn` 前仍需做更稳健的 attachment token 识别
2. “带斜杠的概念枚举”不应默认落入本地文件附件契约

### 3. `deep_research` 对 contract completeness 更敏感

当 prompt 没有清晰给出：

- 决策目标
- audience

时，`deep_research` 更容易进入：

- `clarify`
- `summary_missing_grounding`

当把这两个字段直接前置进消息体后，研究任务可稳定进入：

- `route = deep_research`
- `phase = progress`
- `await_job_completion`

## 结论

本次真正修掉的是：

1. live runtime allowlist 漂移

本次额外暴露出的研究 runtime 问题有两项：

1. slash-like 概念枚举误伤附件契约
2. 研究任务对 contract completeness 的约束较强

后续如果要把 `report_grade / deep_research` 当成稳定研究入口，建议把这两项产品行为纳入下一轮收敛。
