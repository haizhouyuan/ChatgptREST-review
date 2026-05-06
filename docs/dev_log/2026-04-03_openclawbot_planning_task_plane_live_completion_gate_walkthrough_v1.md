# 2026-04-03 OpenClawBot Planning Task Plane Live Completion Gate Walkthrough v1

## 做了什么

1. 修了 runner：
   - 非绿返回非零退出码
   - `manifest.ok` 反映真实 gate 结果
   - 支持 `CHATGPTREST_EVAL_OUT_DIR` 隔离输出目录
2. 修了 gate：
   - bootstrap 失败会出结构化 `ask_failed`
   - bootstrap 后 probe/polling 失败会出结构化 `probe_failed`
3. 现场重跑 live gate，确认现在是可信 fail-closed

## 现场结论

现在能明确区分两类问题：

1. gate 自己的假绿问题
2. 真实 live bootstrap 问题

前者已经修掉；后者还在。
