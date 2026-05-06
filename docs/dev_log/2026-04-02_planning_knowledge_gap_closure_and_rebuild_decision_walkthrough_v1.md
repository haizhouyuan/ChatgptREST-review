# 2026-04-02 Planning Knowledge Gap Closure And Rebuild Decision Walkthrough v1

## 本次做了什么

1. 基于已经完成的代码核验、定向 pytest、offline validation、live query smoke、manifest import 结果，新增一份“补齐还是重构”的决策稿。
2. 把前面分散在多份调查文档里的验证结论压成一个更适合 second-opinion reviewer 阅读的行动判断。

## 为什么要补这份文档

前面的文档已经覆盖了：

1. 能力存不存在
2. 对 planning 有没有价值
3. 实际验证结果怎么样

但还缺一份直接回答这句核心问题的文档：

> 既然已经验证了效果，那现在应该补齐还是重构？

这份文档就是把这个问题单独冻结下来，方便后续让 Claude 做独立核验。

## 这份文档的主判断

1. `planning` 知识主线当前不该重构，应按最小闭环原则补齐。
2. `work memory` 已过“真可用”门槛，应补 ingress / writeback / checkpoint 接线。
3. `runtime pack` 结构成立，但 freshness、acceptance、promotion 没闭环。
4. `KB / vector / graph` 应保留为支撑层，而不是继续膨胀成 planning 主线。

## 输出文件

1. [2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_knowledge_gap_closure_and_rebuild_decision_v1.md)
