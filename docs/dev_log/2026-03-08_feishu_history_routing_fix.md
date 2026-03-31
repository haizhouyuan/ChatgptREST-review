# 2026-03-08 Feishu History Routing Fix

## 背景

在 OpenMind v3 的 Feishu 历史消息模拟里，3 条真实业务风格消息出现了两类误路由：

- 奖励积分系统需求被判成 `WRITE_REPORT -> report`
- 投研框架重构消息被判成 `BUILD_FEATURE -> funnel`

这不是 harness 断言问题，而是 `chatgptrest/advisor/graph.py:analyze_intent()` 的语义加权过粗：

- 把 `儿童心理发展` 里的 `发展` 误计为报告信号
- 把任何以 `把...`、`帮我...` 开头的命令式语句都强推给 `BUILD_FEATURE`

## 修复

### 1. 收紧报告信号

- 删除过宽的裸词 `发展`
- 改成更具体的 `发展趋势`
- 新增 `现状摘要` 这种更贴近真实交付物的报告信号

### 2. 增强业务语义判别

- 增加 `项目卡`、`任务拆分`、`任务分解`、`需求拆解`、`MVP`、`验收标准`、`小应用` 等 build deliverable 信号
- 增加 `先做研究判断`、`只做研究`、`不写正式汇报`、`不写报告` 等 research disambiguation 信号

### 3. 收紧命令式 bonus

- 命令式 bonus 不再对所有 `把...` / `帮我...` 生效
- 只有已经命中 build 语义时，才额外加 `BUILD_FEATURE` 分

## 新增防回归

在 `tests/test_advisor_graph.py` 新增两条单测：

- 奖励积分系统 + 项目卡请求应判为 `BUILD_FEATURE`
- 明确写着“先做研究判断，不写正式汇报”的投研请求应判为 `DO_RESEARCH`

## 验证

执行：

```bash
./.venv/bin/pytest -q tests/test_advisor_graph.py
./.venv/bin/pytest -q tests/test_phase3_integration.py tests/test_feishu_async.py tests/test_feishu_webhook_security.py tests/test_advisor_v3_end_to_end.py
```

结果：全部通过。

## 结论

这次改动不追求“把所有复杂业务话术都完美分类”，只解决已经被 Feishu 历史消息真实打中的两类系统性偏差：

- report 信号过宽
- imperative bonus 过强

当前行为已经回到更符合业务意图的区间，可继续用 Feishu 历史消息做闭环验证。
