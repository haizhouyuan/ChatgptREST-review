# 2026-04-02 Planning Agent Nontechnical Overview Walkthrough v1

## 本轮做了什么

新增一份给用户阅读的非技术版说明书：

1. [2026-04-02_planning_agent_nontechnical_overview_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_agent_nontechnical_overview_v1.md)
2. 本 walkthrough

并已导出同名 `docx`：

- [2026-04-02_planning_agent_nontechnical_overview_v1.docx](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_agent_nontechnical_overview_v1.docx)

## 为什么做

虽然前面已经积累了很多 review 和 policy 文档，但它们主要是给架构收口、规则冻结和后续落地用的。

用户明确反馈：

1. 文档太多
2. 技术门槛太高
3. 更需要一个“通俗易懂版本”

所以这轮的目标不是再写一份技术稿，而是把整件事压成一份：

- 用户能直接读懂
- 能理解为什么之前会乱
- 能理解现在到底定了什么
- 能理解接下来怎么走

## 这份文档怎么组织

正文按下面顺序展开：

1. 我们到底在做什么
2. 为什么之前会乱
3. 这次怎样一步步收口到现在
4. 现在已经定下来的核心方案
5. 为什么没有强推飞书做唯一主入口
6. Anthropic harness 现在放在什么位置
7. 当前进展
8. 下一步建议
9. 一句话总结
10. 你现在最需要记住的 5 句话

## 写作原则

这份稿子刻意遵守下面的约束：

1. 少术语
2. 术语出现时用通俗解释
3. 不按代码模块写
4. 不按端口和 API 写
5. 以“你现在怎么理解这件事”为中心

## 结果

这次 `docx` 导出使用了 `report-pro-suite`，实际成功后端是：

- `pandoc`

导出运行目录是：

- `/tmp/report_pro_suite_outputs/20260402-planning-agent-nontechnical-overview-2026-04-02-r01/fallback-20260402_150341_571/`

这份说明书的作用不是替代前面的技术文档，而是作为：

- 这一轮 planning agent 讨论的非技术总说明

后面你在 Drive 上先读这个版本，再回到技术文档，会轻松很多。
