# Dashboard P0 Fixes — claudeminmax Task Spec

## 背景
ChatGPT Pro (25min thinking, 12.2KB) 对 Dashboard UX 做了深度代码评审。以下 5 项是经代码核验确认的 P0 优先级修复。

## 仓库
`/vol1/1000/projects/ChatgptREST`

## 修改范围

### Fix 1: 拆分 investor shell，去掉 operator chrome

**问题**: Investor 页面仍然套在 "Operator Dashboard" shell 里，导航混用 operator tabs（Overview, Runs, Runtime, Incidents, Cognitive, Graph）和 investor tabs。产品身份矛盾。

**文件**:
- `chatgptrest/dashboard/templates/base.html` — 当前硬编码 "Operator Dashboard"（L15-25）, 有 meta-strip 包含 Raw JSON、Root Runs、Source URL、Page URL（L36-60）
- `chatgptrest/dashboard/routes_dashboard.py` — nav generator 在 L91-127 混合 operator + investor 页面

**改法**:
1. 创建 `chatgptrest/dashboard/templates/investor_base.html`：
   - 复制 `base.html` 但去掉：`Operator Dashboard` 标题、operator tabs（Overview, Runs, Runtime, Incidents, Cognitive, Graph）、Raw JSON 按钮、meta-strip 中 Root Runs/Source/Page
   - 保留：investor 核心导航（Investor Home, Theme Detail, Opportunity Detail, Source Detail）、CSS/JS
2. 修改 `routes_dashboard.py`：investor 相关路由（`investor`, `investor_theme_detail`, `investor_opportunity_detail`, `investor_source_detail`）使用 `investor_base.html`

### Fix 2: 停止全页 auto-refresh → 增量刷新

**问题**: `base.html` L9-26 设置 `data-refresh-seconds="30"`，`dashboard.js` L23-27 读这个值然后执行全页重载。这破坏用户的阅读、滚动位置、graph 选中状态。

**文件**:
- `chatgptrest/dashboard/templates/base.html` — 去掉 `data-refresh-seconds="30"` 属性
- `chatgptrest/dashboard/static/dashboard.js` — L23-27 读 `data-refresh-seconds` 的 `setInterval` 重载逻辑，改为 fetch + DOM patch
- `chatgptrest/dashboard/templates/investor_base.html` — 同上

**改法**:
1. 替换全页 reload 为 `fetch('/v2/dashboard/api/status')` + JSON → 局部 DOM 更新
2. 保留 scroll position、expanded/collapsed sections、graph selection
3. 在页面右上角显示 `Updated Xs ago` 徽章

### Fix 3: 每个页面加一个 primary CTA

**问题**: CSS 定义了 `.primary-button`（`dashboard.css:101-124`）但 investor 模板从未使用。所有"动作"都是 `Open X` 链接，没有主操作。

**文件**:
- `chatgptrest/dashboard/templates/investor_opportunity_detail.html` — 根据 `next_action` 字段渲染一个 `.primary-button`
- `chatgptrest/dashboard/templates/investor_theme_detail.html` — 同上
- `chatgptrest/dashboard/templates/overview.html` — operator pages 根据 `problem_class` 渲染 `Assign`/`Restart`/`Acknowledge`

**改法**:
1. 在 opportunity detail 页顶部 hero 区域加一个 primary CTA：
   - 如果 `next_action` 存在 → 显示 `next_action` 按钮
   - 否则根据 `route` → `Continue Research` / `Wait` / `Drop Thesis`
2. 在 operator overview 里每个问题卡片加一个 action 按钮

### Fix 4: 语言策略 + 降级未解释分数

**问题**: 页面中英混用，且多个内部术语暴露给用户（`residual class`, `expression tradability`, `track record label`, `accepted routes`）。分数字段如 `Ranking Score`, `Quality / Trend`, `distance_to_action` 无任何解释。

**文件**:
- `chatgptrest/dashboard/templates/investor.html` — L16-18, 30-35 中英混用
- `chatgptrest/dashboard/templates/investor_opportunity_detail.html` — L27-28, 44-45 内部术语
- `chatgptrest/dashboard/templates/investor_source_detail.html` — L35-37 内部术语
- `chatgptrest/dashboard/static/dashboard.css` — 分数卡片样式

**改法**:
1. 统一为中文（或英文），去掉混用
2. 对每个分数字段加 `title` 属性做 tooltip，内容为"**来源**: XX / **算法**: XX / **更新时间**: XX"
3. 将 `residual class`, `expression tradability`, `track record label`, `accepted routes` 改为更直白的中文术语，或移到二级折叠区

### Fix 5: 压缩 detail pages

**问题**: opportunity detail HTML 496 行，同时展示 thesis、decision、history diff、claim ledger、skeptic notebook、expression comparison、citation register、source scorecard。

**文件**:
- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`

**改法**:
1. 第一屏只展示：thesis truth, current decision, why not yet, next proof, kill condition, freshness, top evidence
2. 其余内容（claim lane, skeptic lane, expression lane, citation register, source scorecard）用 `<details>` 折叠

## 测试

```bash
# 跑全量测试确保无回归
cd /vol1/1000/projects/ChatgptREST
./.venv/bin/pytest -q

# 手动验证
# 访问 http://127.0.0.1:18711/v2/dashboard/investor 确认无 operator chrome
# 确认页面不再全页刷新
# 确认每个 detail 页都有一个 primary 按钮
```

## 提交规范
- 每个 Fix 单独 commit（`fix(dashboard): split investor shell from operator` 等）
- 全部完成后 push 到 feature branch `feat/dashboard-p0-fixes`
- PR 描述引用本 task spec 文件
