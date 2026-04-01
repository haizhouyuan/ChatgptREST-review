# Gemini Deep Research UI Probe Fix Report (2026-02-24)

## 1) 背景与现象

- 时间窗口：`2026-02-24`。
- 关键失败现象：Gemini DR 在 send 阶段报错
  - `RuntimeError: Gemini tool not found: (Deep Research|深入研究|深度研究)`
- 典型失败 job（修复前复验）：
  - `09ff125c96ce434894817dba91d1d905`
  - 事件：`status_changed: in_progress -> error`
  - 证据：`artifacts/jobs/09ff125c96ce434894817dba91d1d905/debug/20260224_124402_gemini_web_deep_research_error_4924.*`

## 2) 根因

- `_gemini_open_tools_drawer` 的“菜单已打开”判定存在假阳性：
  - 使用了 `text=Deep Research` / `text=生成图片` 这类 marker；
  - 仅检查 `count()`，未校验元素可见性；
  - 页面上存在隐藏文本节点时，会误判“菜单已开”。
- 误判后 `_gemini_find_tool_item` 进入查找，但目标菜单并未真实展开，最终触发 `Gemini tool not found`。
- 同时 `_gemini_find_tool_item`/`_gemini_select_tool` 只取 `.first`，当首个命中元素不可见时会漏掉后续可见项。

## 3) 修复内容

### 3.1 可见性判定修复

- 文件：`chatgpt_web_mcp/providers/gemini/core.py`
- 新增辅助：
  - `_gemini_locator_has_visible(...)`
  - `_gemini_first_visible(...)`
- `_gemini_open_tools_drawer` 改动：
  - 移除 `text=Deep Research` / `text=生成图片` 的 opened marker；
  - opened 判定统一改为“存在可见元素”；
  - 按可见+可用优先点击 tools 按钮。

### 3.2 工具项选择稳健性修复

- 文件：`chatgpt_web_mcp/providers/gemini/core.py`
- `_gemini_select_tool` 和 `_gemini_find_tool_item` 改为“扫描可见项”，不再依赖单一 `.first`。
- 新增 Deep Research 模糊匹配兜底：
  - `_gemini_tool_label_matches(...)`
  - `_gemini_is_deep_research_label_pattern(...)`
  - `_GEMINI_DEEP_RESEARCH_TOOL_FALLBACK_RE`

### 3.3 标签与错误分类增强

- 文件：`chatgpt_web_mcp/providers/gemini/deep_research.py`
  - Deep Research label regex 扩展至简繁体“调研”变体。
- 文件：`chatgpt_web_mcp/providers/gemini_helpers.py`
  - 新增错误类型：`GeminiDeepResearchToolNotFound`。

## 4) 测试与回归

- 运行：
  - `./.venv/bin/pytest -q tests/test_gemini_tools_menu_selectors.py tests/test_gemini_mode_selector_resilience.py`
  - `./.venv/bin/pytest -q tests/test_gemini_wait_transient_handling.py tests/test_mcp_gemini_ask_submit.py tests/test_provider_modules_no_missing_globals.py`
- 结果：全部通过。

新增/更新的测试点：

- `tests/test_gemini_tools_menu_selectors.py`
  - 断言 open marker 包含 `menuitemcheckbox`；
  - 断言不再使用 `text=Deep Research`。
- `tests/test_gemini_mode_selector_resilience.py`
  - `GeminiDeepResearchToolNotFound` 分类；
  - Deep Research 模糊标签匹配（`深度调研`/`深入調研`）。

## 5) 线上复验

- 先重启相关服务，使修复代码生效：
  - `chatgptrest-driver.service`
  - `chatgptrest-worker-send.service`
  - `chatgptrest-worker-wait.service`

- 修复后复验 job：
  - `50c4a64a587c463bba06a68a3407f726`
  - 关键事件：
    - `phase_changed: send -> wait`
    - `wait_requeued`
  - 结果：已不再出现 send 阶段 `Gemini tool not found`，说明根因已命中并修复。

## 6) 余项（P1）

- 仍需补一条“DR 导出 Google Doc -> 从 GDrive 拉取”兜底链路，用于 wait 长轮询不收敛时的收口：
  - 触发条件：`deep_research=true` 且 wait 超时/无进展；
  - 动作：UI 触发导出到 Google 文档 + rclone 侧拉取最新文档；
  - 结果：将导出文本作为 answer fallback 并标记来源。

