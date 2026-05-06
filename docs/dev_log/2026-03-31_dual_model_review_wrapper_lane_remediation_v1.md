# 2026-03-31 Dual-Model Review Wrapper Lane Remediation v1

## 背景

在 `Agent Harness` 双模型评审任务中，封装好的 review workflow 没有真正跑通：

- ChatGPT Pro wrapper lane 失败：`Cannot find prompt textarea. Are you logged in?`
- GeminiDT wrapper lane 失败：`GeminiImportCodeUnavailable`

这轮的目标不是继续绕过，而是修复 ChatgptREST 自己的封装 lane，让 review repo + wrapper + public advisor-agent/MCP 的标准链路恢复可用。

## 根因

### 1. ChatGPT Pro

根因不是 prompt selector 坏，而是 CDP 路径里强制 `new_page() + goto(chatgpt.com)`。

在当前 dedicated driver lane 上：

- 现有已登录 ChatGPT tab 是健康的，prompt selector 可以命中。
- 新开 fresh tab 后再 `goto(chatgpt.com)`，会命中 Cloudflare / `Just a moment...`，从而让 prompt box 全部不可见。

因此，真正的问题是 **CDP 页面获取策略**，不是 selector。

### 2. GeminiDT

根因不是 `gemini_web.ask` lane 不可达，而是 review/public-repo 场景把 imported-code 做成了硬依赖。

本次 review 任务同时具备：

- public `github_repo`
- review packet attachments

在这种场景下，即使 Gemini 的 imported-code 工具不可用，只要 review packet 已经挂载，lane 仍然可以继续停留在 `gemini_web.ask`，不该直接报错退出。

因此，真正的问题是 **imported-code 不可用时没有 review-safe fail-open**。

## 代码改动

### ChatGPT

文件：

- `chatgpt_web_mcp/_tools_impl.py`

改动：

- 新增 `_chatgpt_reuse_existing_cdp_page()`
- 新增 `_chatgpt_has_visible_prompt_box()`
- 新增 `_chatgpt_pick_existing_cdp_page()`
- `_open_chatgpt_page()` 在 CDP 模式下现在优先复用现有健康 ChatGPT tab
  - 无 `conversation_url` 时优先选择“非 Cloudflare + prompt 可见”的页面
  - 有 `conversation_url` 时优先选择匹配同一 conversation 的页面
  - 仅在没有合适现有页时才 `new_page()`

### Gemini

文件：

- `chatgpt_web_mcp/providers/gemini/core.py`
- `chatgpt_web_mcp/providers/gemini/ask.py`

改动：

- 新增 `_gemini_import_code_fail_open()`
- 新增 `_gemini_import_code_fallback_allowed()`
- 新增 `_gemini_maybe_import_code_repo()`
- `gemini_web_ask*` 四条 ask 路径统一改成：
  - 优先尝试 imported-code
  - 若报 `GeminiImportCodeUnavailable`
  - 且同时满足：
    - `github_repo` 存在
    - review packet `drive_files` 已存在
  - 则 fail-open，继续使用 `gemini_web.ask`
  - 并在结果里写入 `import_code_fallback`

## 文档同步

同步更新：

- `skills-src/chatgptrest-call/SKILL.md`
- `.agents/workflows/code-review-upload.md`

新增说明：

- ChatGPT Pro review 在 CDP 模式下优先复用健康 tab，避免 fresh-tab Cloudflare。
- Gemini imported-code review 只在“repo URL + review packet attachments”都存在时允许 review-safe fail-open。

## 测试

新增：

- `tests/test_chatgpt_cdp_page_reuse.py`

扩展：

- `tests/test_gemini_mode_selector_resilience.py`

实际回归命令：

```bash
cd /vol1/1000/projects/ChatgptREST && ./.venv/bin/pytest -q \
  tests/test_chatgpt_cdp_page_reuse.py \
  tests/test_gemini_mode_selector_resilience.py \
  tests/test_skill_chatgptrest_call.py \
  tests/test_mcp_gemini_ask_submit.py \
  -k 'chatgpt or gemini or review_packet or import_code'
```

结果：

- `46 passed`

另外已执行：

```bash
cd /vol1/1000/projects/ChatgptREST && python3 -m py_compile \
  chatgpt_web_mcp/_tools_impl.py \
  chatgpt_web_mcp/providers/gemini/core.py \
  chatgpt_web_mcp/providers/gemini/ask.py \
  tests/test_chatgpt_cdp_page_reuse.py \
  tests/test_gemini_mode_selector_resilience.py
```

结果：

- 通过

## 边界

这轮没有修改：

- review repo 打包逻辑
- public advisor-agent 路由策略
- Gemini CLI 路径
- 浏览器直连 fallback 逻辑之外的外部平台行为

这轮只修复：

- 封装好的双模型 review lane 在当前 live 驱动配置下无法正常起跑的内部根因

## 结论

这次修复的目标不是“让浏览器 fallback 更方便”，而是把：

- ChatGPT Pro review
- GeminiDT review

都拉回到 **ChatgptREST 自己的封装 workflow** 上来跑。
