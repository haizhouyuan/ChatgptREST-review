## 背景

机会页和主题页已经能回答：

- 为什么值得看
- 为什么还不能投
- 最佳表达是什么

但 investor dashboard 仍然差两块：

- 首页还不够像真正的一览表
- source 页还不够像“这条 source 值不值得继续占监控 slot”的工作页

这轮的目标是把这两个入口补成真正可用的投资人视图。

## 本轮改动

### 1. Investor 首页

首页新增：

- `Research Coverage Table`

每条主题压成一行，包含：

- `Theme`
- `Posture`
- `Best expression`
- `Why now`
- `Priority signal`
- `Links`

这样首页不再只是卡片，而是可以快速做优先级排序的一览表。

### 2. Source 详情页

source 页新增：

- `Claim count`
- `How to use this source`
- `Keep / Downgrade Decision`

这让 source 页不再只展示统计，而会直接告诉投资人：

- 这条 source 应该怎么用
- 它为什么还值得继续看
- 什么情况下该降级

## live 验证

真实页面：

- `/v2/dashboard/investor`
- `/v2/dashboard/investor/sources/src_broadcom_ir`

当前已经能看到：

- 首页：`Research Coverage Table`
- source 页：`Claim count`、`How to use this source`、`Keep / Downgrade Decision`

## 测试

这轮跑过：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_dashboard_routes.py -k investor_pages_and_reader_routes
```

结果：通过。

## 结论

这轮之后，investor dashboard 四个主要入口都已经具备明确角色：

- 首页：研究一览和优先级排序
- 主题页：主题工作台
- 机会页：analyst dossier
- source 页：source 是否值得继续盯

这让 `finbot` 输出不再只是“有很多页面”，而是形成了更完整的投资研究操作面。
