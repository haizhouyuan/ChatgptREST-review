# 2026-04-03 Gemini Drive Picker Hardening Execution Review v1

## 1. 这批改动解决什么

这批改动不是泛化重构，而是直接对准当前 `OpenClawBot -> planning task plane -> gemini_web.ask` 现场暴露出来的两类 Drive 附件断点：

1. `Gemini upload menu item not found`
2. `Timed out waiting for visible Google Drive picker iframe`

到这一步为止，live root cause 已经不再描述成旧的 `OpenClaw dynamic replay harness fetch failed`。当前更准确的说法是：

1. `OpenClawBot -> plugin -> /v3/agent/turn -> gemini_web.ask` 主链已经能真实创建 session/job
2. 真实阻塞点前移到 Gemini Drive 附件 UI 分支

## 2. 现场证据

本轮重新核了 live 现场，而不是继续沿用旧 artifact 口径。

### 2.1 现场 job 结果

真实 job artifact 已证明当前失败位于 Drive 附件链：

1. `artifacts/jobs/788802ada001416e84b8a51c8ef42b63/result.json`
   - `error_type=GeminiDriveAttachUnavailable`
   - `error=Timed out waiting for visible Google Drive picker iframe.`
2. `artifacts/jobs/f86158de34df4c5ab91b5d25080f6bf5/result.json`
   - `status=cooldown`
   - `error_type=UiTransientError`
   - `error=Gemini upload menu item not found: ...`

### 2.2 live UI 直接证据

本轮直接通过 `CDP Chrome` 打开 Gemini 页面并抓到当前 upload menu 的真实文本。现场可见：

1. `上传文件`
2. `从云端硬盘添加`
3. `更多上传选项`

因此，这一步得到两个明确判断：

1. Drive 菜单项不是产品功能下线
2. 失败更像 UI 点击/等待链脆弱，而不是 capability 缺失

## 3. 代码改动

文件：

- `chatgpt_web_mcp/providers/gemini/core.py`
- `tests/test_gemini_drive_picker_resilience.py`

### 3.1 `core.py`

这次只做窄收口：

1. 新增 `_GEMINI_DRIVE_MENU_ITEM_RE`
   - 显式覆盖 `从云端硬盘添加` 等当前 live 文本
2. 新增 `_GEMINI_MORE_UPLOAD_OPTIONS_RE`
   - 为 `更多上传选项` 提供 fallback
3. 重写 `_gemini_click_upload_menu_item()` 的候选项查找方式
   - 不再只依赖旧的 `button/[role=menuitem] + has_text`
   - 改成扫描可见菜单候选项的 `inner_text / aria-label / title`
   - 找不到时把当前可见 menu labels 回写进错误文本
4. 新增 `_gemini_open_drive_picker()`
   - 把 `open menu -> click drive item -> wait picker` 收成一个带重试的窄 helper
   - 首次失败后重开菜单再试
   - 保留 fail-closed，不做静默跳过
5. `_gemini_attach_drive_file()` 改为调用 `_gemini_open_drive_picker()`
   - 不再内联一段单次脆弱链路

### 3.2 新增测试

`tests/test_gemini_drive_picker_resilience.py` 覆盖：

1. `更多上传选项 -> Drive item` fallback
2. picker iframe 首次超时后会重试
3. 重试耗尽后仍然 fail-closed，并保留原始错误文本

## 4. 验证

本轮跑过并通过：

1. `python3 -m py_compile chatgpt_web_mcp/providers/gemini/core.py tests/test_gemini_drive_picker_resilience.py`
2. `./.venv/bin/pytest -q tests/test_gemini_drive_picker_resilience.py tests/test_gemini_mode_selector_resilience.py tests/test_gemini_drive_attach_urls.py`
3. `./.venv/bin/pytest -q tests/test_gemini_drive_picker_resilience.py tests/test_gemini_mode_selector_resilience.py tests/test_gemini_drive_attach_urls.py tests/test_openclawbot_planning_task_plane_live_completion_gate.py tests/test_openclawbot_planning_task_plane_live_gate.py`

## 5. 当前判断

这批改动的独立判断应冻结成：

1. 当前 live Drive 菜单项是存在的，旧的“功能可能没了”判断不成立
2. 这批代码提高了 `menu item click + picker open` 两段的抗脆弱性
3. 这批改动已经有单测和相关 planning live-gate 回归支撑
4. 但这还不是“live completion gate 已全绿”的证明

## 6. 下一步

这批 commit 之后的下一步不该再回到泛规划，而是：

1. 重新跑 `OpenClawBot planning task plane live completion gate`
2. 看 blocker 是否已从 `Drive attach UI` 前移到更后面的 Gemini 执行阶段
3. 若仍卡住，再把现场 evidence 冻成下一版 review，而不是沿用旧 root cause

## 7. 一句话结论

> 这批不是把 Gemini Drive 附件宣称“修好”，而是把当前最真实的 live 断点收缩成可重试、可诊断、可继续推进的一条窄链路。
