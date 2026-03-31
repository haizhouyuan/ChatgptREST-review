# Dashboard Phase 2: 全量实现计划

## 现状分析

### 已完成 (P0 - 来自 my 分支)
| 修复项 | 文件 | 状态 |
|--------|------|------|
| Shell 拆分 | `investor_base.html` | ✅ 已合并 |
| 增量刷新(基础) | `dashboard.js` + `/api/status` | ✅ 已合并 |
| Primary CTA - Opportunity | `investor_opportunity_detail.html:28` | ✅ 已合并 |
| 术语修复(tool-tip) | 多个模板 | ✅ 已合并 |
| 次级区块折叠 | `<details>` | ✅ 已合并 |

### 已完成 (Codex 声称但需确认) - 实际未合并
| 修复项 | 预期 | 状态 |
|--------|------|------|
| 增量刷新 DOM patch | dashboard.js | ❌ 未实现 |
| CTA - Theme Detail | investor_theme_detail.html | ❌ 未实现 |
| CTA - Source Detail | investor_source_detail.html | ❌ 未实现 |
| CTA - Overview 问题卡 | overview.html | ❌ 未实现 |

---

## 缺口清单 (Gap Analysis)

### 🔴 高优先级 (P1)

#### 1. 增量刷新升级 - DOM Patch
**问题**: 当前只更新时间戳，没有实际刷新内容
**文件**: `chatgptrest/dashboard/static/dashboard.js`
**改动**:
- 增量获取 JSON 数据
- 智能 patch DOM (只更新变化部分)
- 保留 scroll/selection 状态

#### 2. Theme Detail 页主按钮
**文件**: `chatgptrest/dashboard/templates/investor_theme_detail.html`
**改动**:
- 添加 primary CTA 按钮
- 基于 `recommended_posture` 或 `current_posture` 决定标签

#### 3. Source Detail 页主按钮
**文件**: `chatgptrest/dashboard/templates/investor_source_detail.html`
**改动**:
- 添加 primary CTA 按钮
- 基于 source 类型决定动作

#### 4. Overview 问题卡主按钮
**文件**: `chatgptrest/dashboard/templates/overview.html`
**改动**:
- 问题卡改为 primary-button
- 跳转到对应 runs 队列

### 🟡 中优先级 (P2)

#### 5. Canonical State Model - Opportunity
**文件**: `investor_opportunity_detail.html`
**改动**:
- 确定一个主状态字段 (如 `thesis_status`)
- 大字 + 高亮
- 其他字段降级

#### 6. Canonical State Model - Theme
**文件**: `investor_theme_detail.html`
**改动**:
- 确定主状态 (如 `current_posture`)
- 视觉层级分明

#### 7. 词汇表统一
**改动**:
- 全局统一语言 (中或英)
- 移除 `track_record_label`, `expression_tradability` 从 top-level
- Controlled glossary 注释

#### 8. 首页 Decision Queue 改造
**文件**: `investor.html`
**改动**:
- "什么动了 / 为什么重要 / 下一步看什么" 三段式
- 移除 hero-metrics 堆砌

### 🟢 低优先级 (P3 - 后端改动)

#### 9. 停止 Markdown 解析构建 UI
- 需 service.py 改动
- 提升 claim/citation/source 为一级对象

#### 10. 降级 Graph/Reader 工具
- 移到 "Advanced tools" 二级

---

## 详细实现方案

### Phase 2A: 补完缺口 (1天)

```
2A.1 增量刷新 DOM Patch
    - dashboard.js: 添加 fetchAndPatch() 函数
    - 策略: 比较 JSON diff, 只更新变化的 DOM 节点

2A.2 Theme Detail CTA
    - investor_theme_detail.html:23-30 位置添加 primary-button
    - 基于 recommended_posture 决定标签

2A.3 Source Detail CTA
    - investor_source_detail.html 添加 primary-button
    - 基于 source 类型 (watch/drop/continue)

2A.4 Overview CTA
    - overview.html: 问题卡按钮改为 primary-button
    - 跳转到 /v2/dashboard/runs?problem=true
```

### Phase 2B: 状态模型 (1-2天)

```
2B.1 Opportunity 状态模型
    - 确定: decision → confidence → freshness → blocker
    - 视觉: 主状态大字体, 其他降级

2B.2 Theme 状态模型
    - 确定: current_posture → best_expression → why
    - 视觉: 主状态大字体, 其他降级

2B.3 Operator 状态模型
    - 确定: severity → owner → next_step
    - 视觉: 主状态大字体, 其他降级
```

### Phase 2C: 首页重构 (2天)

```
2C.1 Investor 首页 Decision Queue
    - 移除 hero-grid
    - 改为: "What moved" / "Why it matters" / "What to watch"

2C.2 Operator 首页 Triage
    - 改为: "What's broken" / "Who owns" / "What to do"
```

### Phase 2D: 词汇表 (1天)

```
2D.1 语言统一
    - investor 页面: 全英文 (或全中文, 需确认)
    - operator 页面: 全英文

2D.2 术语清理
    - 移除 top-level 晦涩术语
    - 建立 controlled glossary
```

### Phase 2E: 后端 (可选)

```
2E.1 停止 Heuristic 解析
    - service.py: 提升为存储对象

2E.2 降级工具
    - graph/reader 移到二级
```

---

## 测试计划

```bash
# 单元测试
./.venv/bin/pytest -q tests/test_dashboard_routes.py

# 集成测试
./.venv/bin/pytest -q tests/test_finbot_dashboard_service_integration.py

# Lint
node --check chatgptrest/dashboard/static/dashboard.js
```

---

## 分支策略

```bash
# 当前分支
feat/dashboard-p0-fixes-clean (已有 P0 改动)

# 新建继续开发分支
git checkout -b feat/dashboard-phase2-ux-improvements

# 开发完成后合并
git merge feat/dashboard-p0-fixes-clean
# 或 rebase
git rebase master
```

---

## 风险与依赖

1. **DOM Patch 复杂度** - 需确保不破坏现有功能
2. **后端数据模型** - Phase 2E 需 service.py 配合
3. **测试覆盖** - 需补充 CTA 相关测试

---

## 预计工期

| Phase | 工期 | 累计 |
|-------|------|------|
| 2A 补完缺口 | 1天 | 1天 |
| 2B 状态模型 | 1-2天 | 2-3天 |
| 2C 首页重构 | 2天 | 4-5天 |
| 2D 词汇表 | 1天 | 5-6天 |
| 2E 后端(可选) | 2-3天 | 7-9天 |
