# 2026-04-02 Repo Bootstrap And Doc Obligations Scope Walkthrough v1

## 这轮为什么要补这份 review

用户明确提出一个很关键的问题：

1. `repo_bootstrap`
2. `repo_doc_obligations`

这两个工具到底是不是必要的。

这个问题的本质不是“代码能不能跑”，而是：

1. 它们到底服务哪个目标
2. 它们是不是 publicagentmcp 的合理组成部分

## 这轮核到的关键事实

### 1. 这两个工具是近期加进来的

它们来自 `2026-03-31 bootstrap system` 那轮开发，不是远古遗留。

### 2. 它们的真实定位不是 ask facade

它们服务的是：

1. repo cold-start
2. doc/test obligations
3. closeout discipline

也就是 repo maintenance / coding-agent repo cognition。

### 3. 它们的底层能力有用

脚本、CLI、closeout 都已经接上了，说明能力本身不是空壳。

### 4. 但它们不该继续挂在 publicagentmcp 主面

如果 publicagentmcp 的目标是更纯的：

1. `advisor_agent_turn`
2. `status`
3. `cancel`
4. `wait`

ask lifecycle facade，

那这两个工具明显属于另一个面。

## 这轮收口后的判断

最准确的说法不是：

1. “这两个工具没用”
2. “这两个工具必须保留在 publicagentmcp”

而是：

1. 能力层应保留
2. surface placement 应调整

更适合的归宿：

1. script / CLI
2. 或 admin / maint MCP

而不是 publicagentmcp 主 surface。
