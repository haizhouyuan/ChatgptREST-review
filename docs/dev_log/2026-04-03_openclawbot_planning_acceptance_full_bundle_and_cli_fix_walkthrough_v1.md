# 2026-04-03 OpenClawBot Planning Acceptance Full Bundle And CLI Fix Walkthrough v1

## 本次做了什么

1. 检查现有 `openclaw acceptance pack`，确认实现本身已经支持 7 类 scenario
2. 现场重跑 full bundle，确认 `7/7 + branch` 已经真实通过
3. 发现 runner 的实际问题主要不是 pack 本体，而是脚本入口的 import path 依赖当前工作目录
4. 修复 runner 顶层导入路径
5. 把自动测试从“3 类 targeted pack”扩成“3 类 targeted + full bundle + CLI + failure exit code”

## 为什么这一批值得单独落盘

之前 `W1` 其实已经接近做完，但证据和自动化保护还不够：

1. full bundle 已经能跑通，但测试没有锁住
2. direct-python CLI 的入口修法没有自动保障
3. 红队指出测试仍偏 happy path，这一批把主要缺口补上了

## 结果

`W1` 现在的完成度已经明显提升：

1. full bundle evidence 固化
2. runner 入口统一
3. 回归保护更强

下一步应回到 `W2`，不要继续围绕同一 acceptance runner 打转。
