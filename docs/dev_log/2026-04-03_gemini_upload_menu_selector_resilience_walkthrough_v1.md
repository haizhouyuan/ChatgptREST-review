# 2026-04-03 Gemini Upload Menu Selector Resilience Walkthrough v1

## 本次做了什么

完成了一批窄修复：

1. 现场抓 Gemini live DOM
2. 确认 upload menu button 的 label 已漂移
3. 在 provider 侧补新的 selector 变体
4. 新增独立测试文件，避免碰你工作区里已有的 Gemini 脏测试文件

## 为什么做这批

当前 live blocker 一直是：

1. `Gemini upload menu button not found`

但在改代码前，必须先确认到底是：

1. 按钮不存在
2. 菜单项不存在
3. selector 过时

现场结果已经证明：

1. 按钮存在
2. 菜单项也存在
3. selector 过时

## 代码上怎么收

这次没有改大逻辑，只补了 `_GEMINI_UPLOAD_MENU_BUTTON_SELECTORS`。

也就是说：

1. 先让 `_gemini_open_upload_menu()` 能重新看到当前页面按钮
2. 不碰更后面的 Drive picker

## 验证

这次跑过：

1. `python3 -m py_compile chatgpt_web_mcp/providers/gemini/core.py tests/test_gemini_upload_menu_resilience.py`
2. `./.venv/bin/pytest -q tests/test_gemini_upload_menu_resilience.py tests/test_gemini_mode_selector_resilience.py tests/test_gemini_drive_attach_urls.py`

## 当前结论

这批属于：

1. selector resilience 批次
2. 不是 live green 批次

它的作用是把当前 blocker 从“抽象地找不到按钮”推进成“当前按钮 label 漂移已修复，接下来该看更后面的 attach 流程”。
