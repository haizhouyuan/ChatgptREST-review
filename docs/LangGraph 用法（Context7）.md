# LangGraph 用法（Context7）

本文件使用 Context7 MCP 从 LangGraphJS 文档库抽取/整理（libraryId：`/langchain-ai/langgraphjs`），用于快速上手“用图（Graph）编排长程、可恢复、有状态的 agent/workflow”。

来源（Context7 索引）：
- https://github.com/langchain-ai/langgraphjs/blob/main/examples/how-tos/stream-tokens.ipynb
- https://github.com/langchain-ai/langgraphjs/blob/main/examples/how-tos/persistence.ipynb
- https://github.com/langchain-ai/langgraphjs/blob/main/examples/how-tos/tool-calling.ipynb
- https://github.com/langchain-ai/langgraphjs/blob/main/examples/how-tos/tool-calling-errors.ipynb
- https://github.com/langchain-ai/langgraphjs/blob/main/examples/how-tos/subgraphs-manage-state.ipynb
- https://github.com/langchain-ai/langgraphjs/blob/main/examples/how-tos/cross-thread-persistence.ipynb
- https://github.com/langchain-ai/langgraphjs/blob/main/docs/docs/concepts/functional_api.md
- https://github.com/langchain-ai/langgraphjs/blob/main/examples/how-tos/time-travel.ipynb
- https://github.com/langchain-ai/langgraphjs/blob/main/examples/multi_agent/agent_supervisor.ipynb

> 说明：以下示例主要来自 notebook，代码片段可能省略了 `modelWithTools/boundModel/tools` 等外围定义；但核心的 Graph/State/路由/执行方式可直接复用。

## 1) 核心概念（最小集）

- `StateGraph(...)`：用“状态机 + 有向图”方式定义工作流（节点=函数/工具，边=流转规则）。
- `START` / `END`：图的起点/终点常量（也可用 `"__start__"`、`"__end__"`）。
- `addNode(name, fnOrNode)`：新增节点（例如 `agent`、`tools`）。
- `addEdge(from, to)`：固定边。
- `addConditionalEdges(from, routerFn, ...)`：条件路由（常见：看最后一条 AI message 是否有 `tool_calls`）。
- `compile()`：编译为可执行图（得到 `graph/app/agent`）。
- 执行：
  - `graph.invoke(...)`：跑到结束，返回最终 state。
  - `graph.stream(...)`：以 async iterator 方式流式产出中间状态（适合 UI 实时展示）。
- “持久化/恢复”常用入口：在 `RunnableConfig.configurable` 里传 `thread_id`（以及可选的 `checkpoint_id` 等）。

## 2) 定义一个最小 StateGraph（条件路由 + tools 回环）

来自 `stream-tokens.ipynb` 的片段，展示“agent → (tools?) → agent → ... → END”的基本形态：

```typescript
import { StateGraph, END } from "@langchain/langgraph";
import { AIMessage } from "@langchain/core/messages";

const routeMessage = (state: typeof StateAnnotation.State) => {
  const { messages } = state;
  const lastMessage = messages[messages.length - 1] as AIMessage;
  // If no tools are called, we can finish (respond to the user)
  if (!lastMessage?.tool_calls?.length) {
    return END;
  }
  // Otherwise if there is, we continue and call the tools
  return "tools";
};

const callModel = async (state: typeof StateAnnotation.State) => {
  // For versions of @langchain/core < 0.2.3, you must call `.stream()`
  // and aggregate the message from chunks instead of calling `.invoke()`.
  const { messages } = state;
  const responseMessage = await boundModel.invoke(messages);
  return { messages: [responseMessage] };
};

const workflow = new StateGraph(StateAnnotation)
  .addNode("agent", callModel)
  .addNode("tools", toolNode)
  .addEdge("__start__", "agent")
  .addConditionalEdges("agent", routeMessage)
  .addEdge("tools", "agent");

const agent = workflow.compile();
```

## 3) ToolNode + ReAct（常见 agent 模式）

### 3.1 基本 ReAct 形态（`MessagesAnnotation` + `ToolNode`）

来自 `tool-calling.ipynb`：

```typescript
import {
  StateGraph,
  MessagesAnnotation,
  END,
  START
} from "@langchain/langgraph";

const toolNodeForGraph = new ToolNode(tools)

const shouldContinue = (state: typeof MessagesAnnotation.State) => {
  const { messages } = state;
  const lastMessage = messages[messages.length - 1];
  if ("tool_calls" in lastMessage && Array.isArray(lastMessage.tool_calls) && lastMessage.tool_calls?.length) {
      return "tools";
  }
  return END;
}

const callModel = async (state: typeof MessagesAnnotation.State) => {
  const { messages } = state;
  const response = await modelWithTools.invoke(messages);
  return { messages: response };
}

const workflow = new StateGraph(MessagesAnnotation)
  .addNode("agent", callModel)
  .addNode("tools", toolNodeForGraph)
  .addEdge(START, "agent")
  .addConditionalEdges("agent", shouldContinue, ["tools", END])
  .addEdge("tools", "agent");

const app = workflow.compile()
```

### 3.2 显式列出条件分支（便于可视化/调试）

来自 `tool-calling-errors.ipynb` 的 `addConditionalEdges(..., { tools: "tools", __end__: "__end__" })` 用法：

```typescript
  .addConditionalEdges("agent", shouldContinue, {
    tools: "tools",
    __end__: "__end__"
  })
```

## 4) 执行与流式（stream）

### 4.1 用 `thread_id` 跑流式执行（输出每步 update）

来自 `subgraphs-manage-state.ipynb`：

```javascript
const graphStream = await graph.stream({
  messages: [{
    role: "user",
    content: "what's the weather in sf"
  }],
}, {
  configurable: {
    thread_id: "4",
  }
});

for await (const update of graphStream) {
  console.log(update);
}
```

### 4.2 `streamMode: "values"` + 自定义字段（例如 `userId`）

来自 `cross-thread-persistence.ipynb`：

```javascript
let config = { configurable: { thread_id: "1", userId: "1" } };
let inputMessage = { type: "user", content: "Hi! Remember: my name is Bob" };

for await (const chunk of await graph.stream(
  { messages: [inputMessage] },
  { ...config, streamMode: "values" }
)) {
  console.log(chunk.messages[chunk.messages.length - 1]);
}
```

### 4.3 Functional API 的 `stream`（概念示例）

来自 `docs/docs/concepts/functional_api.md`：

```typescript
const config = {
  configurable: {
    thread_id: "some_thread_id",
  },
};

for await (const chunk of await myWorkflow.stream(someInput, config)) {
  console.log(chunk);
}
```

## 5) 持久化 / checkpoint（概念）

LangGraphJS 的一些示例会暴露 “checkpoint 快照” 的结构（包含 `thread_id`、`checkpoint_id`、`parentConfig` 等），便于恢复/分叉执行。来自 `time-travel.ipynb`（节选）：

```json
{
  "metadata": { "source": "loop", "writes": null, "step": 0 },
  "config": {
    "configurable": {
      "thread_id": "conversation-num-1",
      "checkpoint_ns": "",
      "checkpoint_id": "1ef69ab6-8c4b-6261-8000-c51e5807fbcd"
    }
  },
  "parentConfig": {
    "configurable": {
      "thread_id": "conversation-num-1",
      "checkpoint_ns": "",
      "checkpoint_id": "1ef69ab6-8c4b-6260-ffff-6ec582916c42"
    }
  }
}
```

## 6) 运行图（invoke vs stream）

来自 `agent_supervisor.ipynb`（文案摘要）：通常用 `graph.invoke()` 或 `graph.stream()` 运行。
- `invoke`：运行到完成，返回最终 state
- `stream`：返回 async iterator，逐步 yield 中间状态，适合实时应用/可观测性

