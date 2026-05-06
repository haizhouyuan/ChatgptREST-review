# 2026-04-02 Planning Agent Total Plan Addendum: PublicAgentMCP Boundary Walkthrough v1

## 本次做了什么

1. 新增一份总计划补丁，专门处理 `publicagentmcp` 已冻结为 `ask wrapper` 之后的边界问题。
2. 明确把“client 负担”拆成三层：
   - `Thin MCP Runtime`
   - `Planning Agent Policy Layer`
   - `Task Truth Layer`
3. 把后续应补的 3 份 policy 正式纳入总计划：
   - `Lane Policy`
   - `Attachment Preflight Policy`
   - `Fast vs Deep Delivery Policy`

## 为什么要补这份文档

用户明确接受：

1. `publicagentmcp` 不要继续做成大杂烩
2. 但过去往里塞功能是为了减轻 client 使用负担

所以这轮不能只停在“改口”，还必须回答：

> 既然不再让 MCP 变胖，那这些实际使用问题后面谁来解决？

这份文档就是把这个责任重新分配清楚。

## 输出文件

1. [2026-04-02_planning_agent_total_plan_addendum_publicagentmcp_boundary_v1.md](/vol1/1000/projects/ChatgptREST/docs/reviews/2026-04-02_planning_agent_total_plan_addendum_publicagentmcp_boundary_v1.md)
