# 2026-04-03 Gemini Upload Menu Selector Resilience Walkthrough v2

## 本次相对 v1 又收了什么

`v1` 的方向是对的，但红队指出两点：

1. 测试太“假”，只是 selector 字符串命中
2. 没有证明多个候选按钮并存时不会误点

这次 `v2` 就只收这两件事。

## 代码上怎么收

运行时代码没有扩大逻辑，只做两件事：

1. 把 current exact label 放到更高优先级
2. 保留 substring selector 作为兜底

## 测试怎么补

这次把测试换成了更像真实 DOM 的 fake：

1. 用按钮对象的 `aria_label` 做匹配
2. 解析 exact / contains / case-insensitive contains selector
3. 新增多候选按钮并存的负向测试

## 验证

这轮实际跑过：

1. `python3 -m py_compile chatgpt_web_mcp/providers/gemini/core.py tests/test_gemini_upload_menu_resilience.py`
2. `./.venv/bin/pytest -q tests/test_gemini_upload_menu_resilience.py tests/test_gemini_mode_selector_resilience.py tests/test_gemini_drive_attach_urls.py`

## 当前结论

这批现在更适合被表述成：

1. selector resilience 已补
2. live gate 仍待重跑
3. 当前还不能宣称 upload-menu 阶段已经完全越过
