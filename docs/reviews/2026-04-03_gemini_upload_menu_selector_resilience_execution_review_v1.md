# 2026-04-03 Gemini Upload Menu Selector Resilience Execution Review v1

## 1. 这批改动解决什么

这批不是去改 Gemini Drive picker 本身，而是收一个更靠前、更明确的 live blocker：

> `Gemini upload menu button not found`

现场已经证明：

1. 真实页面上“打开菜单”的按钮是存在的
2. 但它当前的可访问名已经不是代码里硬编码的 `Open file upload menu`
3. 所以问题更像 selector 漂移，不像权限或地区限制

## 2. 现场证据

这轮直接对 live Gemini 页面做了快照：

1. 当前页面 URL：
   - `https://gemini.google.com/app`
2. composer 附近实际按钮的可访问名是：
   - `打开输入区域菜单，以选择工具和上传内容类型`
3. 点开后实际菜单项存在：
   - `上传文件`
   - `从云端硬盘添加`

所以当前更精确的判断是：

1. menu item 并没有先漂
2. 更先漂的是“打开菜单”这个按钮的 label

## 3. 代码改动

文件：

- `chatgpt_web_mcp/providers/gemini/core.py`

本次只做窄修复：

1. 在 `_GEMINI_UPLOAD_MENU_BUTTON_SELECTORS` 里补上新的 composer-menu label 变体
2. 不改 Drive picker
3. 不改 attach fallback 语义
4. 不改 executor / route / task plane

新增覆盖的 selector 重点是：

1. `button[aria-label*='输入区域菜单']`
2. `button[aria-label*='上传内容类型']`
3. `button[aria-label*='input area menu' i]`
4. `button[aria-label*='upload content type' i]`

## 4. 新增验证

新增测试文件：

- `tests/test_gemini_upload_menu_resilience.py`

覆盖：

1. 中文新 label 可以被 `_gemini_open_upload_menu()` 命中
2. 英文 `input area menu` 变体也可以被命中

并回归：

1. `tests/test_gemini_mode_selector_resilience.py`
2. `tests/test_gemini_drive_attach_urls.py`

## 5. 当前判断

这批的独立判断是：

1. 当前 `upload menu button not found` 已经有非常具体的 selector-level 根因
2. 这批修复足够窄，风险低
3. 它有希望推动 live blocker 继续向后暴露
4. 但在重跑 live gate 之前，还不能把它说成“已完成 live 修复”

## 6. 下一步

下一步最该做的是：

1. 重启相关 Gemini 执行面
2. 重跑 live completion gate
3. 看 blocker 是否从“找不到 upload menu button”推进到更后面的 attach/picker 阶段

## 7. 一句话结论

这批修复的核心不是“Drive attach 已经修好”，而是：

> 已经把当前最前面的 live selector 漂移点收到了明确的 composer-menu label 上，并补了低风险 selector resilience 修复。
