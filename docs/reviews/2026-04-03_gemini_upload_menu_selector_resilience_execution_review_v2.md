# 2026-04-03 Gemini Upload Menu Selector Resilience Execution Review v2

## 1. v2 相比 v1 收紧了什么

`v2` 继续只做证据和口径收口，不扩大功能面。

这次补上的两点是：

1. 测试不再把 selector 字符串直接当 key，而是模拟真实 `aria-label` 匹配
2. 新增了“多个候选按钮并存时，优先点 current exact label”的负向测试

## 2. 这批改动解决什么

这批仍然不是去改 Gemini Drive picker 本身，而是收一个更靠前、更明确的 live blocker：

> `Gemini upload menu button not found`

现场已经证明：

1. 真实页面上“打开菜单”的按钮是存在的
2. 当前可访问名已经不是旧代码硬编码的 `Open file upload menu`
3. menu item 本身并没有先漂
4. 所以当前最前面的根因更像 selector 漂移，不像权限或地区限制

## 3. 现场证据

这轮直接对 live Gemini 页面做了快照：

1. 当前页面 URL：
   - `https://gemini.google.com/app`
2. composer 附近实际按钮的可访问名是：
   - `打开输入区域菜单，以选择工具和上传内容类型`
3. 点开后实际菜单项存在：
   - `上传文件`
   - `从云端硬盘添加`

因此当前更准确的判断是：

1. menu item 并没有先漂
2. 更先漂的是“打开菜单”这个按钮的 label

## 4. 代码改动

文件：

- `chatgpt_web_mcp/providers/gemini/core.py`

本次仍然只做窄修复：

1. 在 `_GEMINI_UPLOAD_MENU_BUTTON_SELECTORS` 里补上 current exact label 与对应兜底变体
2. 优先 exact current label，再退回到较宽的 substring selector
3. 不改 Drive picker
4. 不改 attach fallback 语义
5. 不改 executor / route / task plane

新增覆盖的 selector 重点是：

1. `button[aria-label='打开输入区域菜单，以选择工具和上传内容类型']`
2. `button[aria-label='Open input area menu to select tools and upload content types']`
3. 中文/英文 substring 兜底变体

## 5. 新增验证

新增测试文件：

- `tests/test_gemini_upload_menu_resilience.py`

现在覆盖：

1. current Chinese live label 可以被 `_gemini_open_upload_menu()` 命中
2. current English exact phrase 也可以被命中
3. 多个候选按钮并存时，会优先点击 current exact label，不会先误点 generic substring match

并回归：

1. `tests/test_gemini_mode_selector_resilience.py`
2. `tests/test_gemini_drive_attach_urls.py`

## 6. 当前判断

这批的独立判断现在应当冻结成：

1. 当前 `upload menu button not found` 已经被缩小到 selector-level 漂移
2. 这批修复提供了一层低风险 selector resilience
3. 但在新的 live gate 之前，还不能把它说成“已证明 blocker 已越过 upload-menu 阶段”

## 7. 下一步

下一步最该做的是：

1. 重启相关 Gemini 执行面
2. 重跑 live completion gate
3. 看 blocker 是否已经越过 upload-menu 阶段，并进入 picker modal / search / insert

## 8. 一句话结论

这批修复的核心不是“Drive attach 已经修好”，而是：

> 已经把当前最前面的 live selector 漂移点收到了 composer-menu label 上，并补了一层更有证据支撑的低风险 selector resilience。
