# LangChain - Deep Agents

- source_url: https://www.langchain.com/deep-agents
- fetched_at: 2026-03-31T12:46:13+08:00
- extract_method: jina

Title: LangChain Deep Agents: Build Agents for Complex, Multi-Step Tasks

URL Source: https://www.langchain.com/deep-agents

Published Time: Mon, 30 Mar 2026 06:17:49 GMT

Markdown Content:
![Image 1](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/69999dae51418243b721e2e3_Frame%202147255016.svg)

Deep Agents

Deep Agents is an open source agent harness built for long-running tasks. It handles planning, context management, and multi-agent orchestration for complex work like research and coding.

![Image 2](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/699eaa174b3d30f7c7993d0a_deepagents%20ilu.svg)

## Why use Deep Agents?

### Designed for autonomous agents

Agents are taking on increasingly complex work over long time horizons, like research, coding, and multi-step workflows. Deep Agents provides the primitives for these patterns:

*   **Break down complex objectives:**_Planning tools let agents decompose tasks, track progress, and adapt as they learn_
*   **Delegate work in parallel:**_Spawn subagents for independent subtasks, each with isolated context_
*   **Persist knowledge across sessions:**_Virtual filesystem stores system prompts, skills, and long-term memory_

[Learn about the agent harness](https://docs.langchain.com/oss/python/deepagents/harness)

![Image 3](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/6999a0bed2f79ae5467ae2be_Eval_2-2.avif)![Image 4](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/69982183c78f464d8485ff43_glow.avif)

### Native context management

Context management is critical for long-running agents, and hard to get right. Deep Agents includes middleware that helps agents compress conversation history, offload large tool results, isolate context with subagents, and use prompt caching to reduce latency and cost.

[Context management with deep agents](https://blog.langchain.com/context-management-for-deepagents/)

![Image 5](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/6999a0be575e3305fd8a3d58_dd71ede3670662aea274e86aa82ef40e_Eval_2-1.avif)![Image 6](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/69982183c78f464d8485ff43_glow.avif)

### Model neutral with maximum configurability

Deep Agents is a batteries-included, general purpose agent harness. Use any model provider, manage state, and add human-in-the-loop when you need it. Tracing and deployment work natively with LangSmith.

[Deploy deep agents with LangSmith](https://www.langchain.com/langsmith-platform)

![Image 7](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/6999a0bef56ac8c7eb734c1d_de3e8cf95f8471b43cbae824c0fe3609_Eval_2.avif)![Image 8](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/69982183c78f464d8485ff43_glow.avif)

### Code with Deep Agents CLI

Deep Agents is available as an SDK and CLI, so you can use it in your codebase or run it directly in your terminal.

[Learn more about Deep Agents CLI](https://docs.langchain.com/oss/python/deepagents/cli)

![Image 9](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/6999a0bed97d88401ea13ab5_graphic.avif)![Image 10](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/69982183c78f464d8485ff43_glow.avif)

![Image 11](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/69a025b1c2c9ee3fcc4c8189_LangChain_academy.svg)

#### Deep Agents

[![Image 12](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/69a047c394793b4a6b6a7a45_4486f48551ac550292df72164c412c24_module3.avif)](https://academy.langchain.com/courses/deep-agents-with-langgraph)
Learn about the fundamental characteristics of Deep Agents - including planning, memory, and subagents - and how to implement your own Deep Agent for complex, long-running tasks.

[Take the course](https://academy.langchain.com/courses/deep-agents-with-langgraph)

![Image 13](https://cdn.prod.website-files.com/65b8cd72835ceeacd4449a53/6999965e520db9b0ccefdaa3_langchain%20vis.png)

### FAQs for Deep Agents

What is an agent harness?

Agent harnesses are opinionated agent frameworks with that come batteries included with built-in tools and capabilities that make building sophisticated, long-running agents easier.[Learn more](https://docs.langchain.com/oss/python/concepts/products#agent-harnesses-like-the-deep-agents-sdk).

When should I use Deep Agents vs other LangChain frameworks?

Use Deep Agents when you want to build an autonomous agent to handle complex, non-deterministic, and long running tasks.

Choose LangGraph when you want low-level control for building stateful, long-running workflows and agents.

Choose LangChain when you want a quick way to get started and to standardize how teams build agent patterns.

[Learn more](https://docs.langchain.com/oss/python/concepts/products#when-to-use-the-deep-agents-sdk) about when to choose each LangChain framework.[](https://docs.langchain.com/oss/python/concepts/products#feature-comparison)

‍

How does Deep Agents compare to other agent harnesses?

Visit [this page](https://docs.langchain.com/oss/python/deepagents/comparison) for a detailed comparison of features across Deep Agents, OpenCode, and Claude SDK.

### S

e

e

w

h

a

t

y

o

u

r

a

g

e

n

t

i

s

r

e

a

l

l

y

d

o

i

n

g

LangSmith, our agent engineering platform, helps developers debug every agent decision, eval changes, and deploy in one click.
