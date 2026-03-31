# LangGraph - Platform GA

- source_url: https://blog.langchain.dev/langgraph-platform-ga/
- fetched_at: 2026-03-31T12:46:13+08:00
- extract_method: jina

Title: LangGraph Platform is now Generally Available: Deploy & manage long-running, stateful Agents

URL Source: https://blog.langchain.dev/langgraph-platform-ga/

Published Time: 2025-05-14T13:55:34.000Z

Markdown Content:
_Note: As of October 2025, LangGraph Platform has been re-named to "LangSmith Deployment"._

Today we’re excited to announce the general availability of [**LangGraph Platform**](https://blog.langchain.com/langgraph-platform-ga/) — our purpose-built infrastructure and management layer for deploying and scaling long-running, stateful agents. Since our beta last June, nearly 400 companies have used LangGraph Platform to deploy their agents into production.

Agent deployment is the next hard hurdle for shipping reliable agents, and LangGraph Platform dramatically lowers this barrier with:

*   **1-click deployment** to go live in minutes,
*   **30 API endpoints**for designing custom user experiences that fit any interaction pattern
*   **Horizontal scaling** to handle bursty, long-running traffic
*   **A persistence layer** to support memory, conversational history, and async collaboration with human-in-the-loop or multi-agent workflows
*   **Native LangGraph Studio**, the agent IDE, for easy debugging, visibility, and iteration

Read on to learn more about what LangGraph Platform offers and which deployment option is right for you. If you're more of a visual learner, you can check out our [video walkthrough here](https://youtu.be/YWVuBLSbNWE?ref=blog.langchain.com).

## **The challenges of agent infrastructure – and how LangGraph Platform can help**

Our team has the privilege of working with [many of the most exciting companies building agents](https://www.langchain.com/built-with-langgraph?ref=blog.langchain.com) – such as Klarna, Lovable, Replit, Clay, LinkedIn. Through close collaboration, we’ve come to believe that the challenges of running agents, at scale, in production are often unique relative to traditional apps:

1.   **Many agents are long running.**Like we’ve seen with deep research agents, agents that run in the background on a schedule or in response to [environment triggers](https://blog.langchain.com/introducing-ambient-agents/) can take a long time to return a final output. These workflows can be prone to failures mid-task, so they need durable infrastructure to ensure task completion.
2.   **Many agents rely on async collaboration.**Agents need to act on inputs from unpredictable events, whether collaborating with a human to steer / approve an action or waiting on another agent. For example – will the human reply immediately, tomorrow, or not at all? Good infrastructure accounts for this chaos and preserves state throughout.
3.   **Bursty.**While not totally unique to agents, horizontally scaling infra to handle traffic spikes is challenging – especially for tasks that run daily or on schedules.

We want engineers to obsess over building the best agent architecture – not worry about infra. LangGraph Platform’s server suits these kinds of workloads at scale. Developers can just 1-click deploy their apps directly in the management console to get started.

![Image 1](https://lh7-rt.googleusercontent.com/docsz/AD_4nXdplpjyQNwUU78XpB_6nQzyOMvB4TqPdABOBlURmqFTIZzlDYsORC4qQ3u5Vf7Yr4Y3qkLp85fE_nMJus7f5CfeWhzIJNFFqov57UIjSyzqAeI6AbwG3MbWfXMsAmcH2BjTrrjK0Q?key=zczEAICBSmAQ0C-sLEdY8w)

1-click deploy with our native GitHub integration —just select a repo, and ship! 

## **Accelerate agent development with visual workflows**

Building great agents requires fast feedback loops.[**LangGraph Studio**](https://langchain-ai.github.io/langgraph/concepts/langgraph_studio/?ref=blog.langchain.com) (included as part of LangGraph Platform) helps developers visualize and debug agent workflows in real time, with detailed visibility into agent trajectories and support for branching logic and retries.

You can also test edge cases, inspect memory/state at each step, and quickly pinpoint where things go wrong. Instead of retrying things from scratch, built-in checkpointing and memory modules in LangGraph Platform make it easy to rewind, edit, and rerun failure points without frustration.

![Image 2](https://lh7-rt.googleusercontent.com/docsz/AD_4nXewyF6mmX7x2huxIkZsH5_M7kSeirMNes1tbhYm2kzQOZjCMPp6PRHLNphT_1_FhL9OV66UsQNmQINU_IWV41olyeT6u_FvQlWhDinFzs6LMc737jx_3PXuXANj2eTBLOtLyOM0fQ?key=zczEAICBSmAQ0C-sLEdY8w)
Whether you’re using our [pre-built agent templates](https://github.com/langchain-ai/open-agent-platform?ref=blog.langchain.com) for common agent workflows, or building from scratch, LangGraph Platform lets you scaffold your agentic apps quickly – going from an idea to production in hours.

## **Centralize agent management across your org**

As agents get adopted across teams, managing them becomes a team sport. LangGraph Platform gives organizations a unified view of every agent in development or production — helping fellow team members iterate and scale across use cases. The enterprise tier also supports RBAC and workspaces, so that you can control access and sharing.

The LangGraph Platform management console makes it easier to enforce consistency, monitor behavior, and ship updates safely — all without needing to re-deploy or touch code every time. You can:

*   Discover available agents in the agent registry
*   Create different versions of your agent (“assistants”) in LangGraph platform, allowing you to reuse common agent architectures
*   Leverage other agents as “Remote Graphs”, allowing you to create multi agent architectures that run in a distributed manner

For companies like Qualtrics, centralizing agent management with LangGraph Platform has been critical to driving efficiency:

> _"The future of agentic AI is multi-vendor and AI agents must be built in an ecosystem. By using LangGraph Platform to build and manage our AI agents - Experience Agents - Qualtrics is able to design, deploy, and manage complex generative AI agent workflows with efficiency, speed, and scale." – Phil McKennan, VP of Strategy and Partnerships at Qualtrics_

## **Try LangGraph Platform today**

LangGraph Platform reduces time to production and enables better application experiences with a runtime that suits the workload and improves DevEx with well crafted APIs, built-in memory, and a Studio development environment. Today, LangGraph Platform is generally available.

To get started, choose the deployment option that fits your team’s needs:

*   **Cloud (SaaS):** Fastest way to get started, fully managed and easy deployment from within LangSmith. Available on our Plus plan and Enterprise plan.To get started, [read the docs](https://langchain-ai.github.io/langgraph/cloud/quick_start/?_gl=1*1b9m3eb*_ga*MTA0MzgxMzQ2OS4xNzM3MDUyNDkw*_ga_47WX3HKKY2*czE3NDcxMDY2MzYkbzQ4JGcxJHQxNzQ3MTA3Mzk4JGowJGwwJGgw&ref=blog.langchain.com) (Plus plan) or[contact sales](https://www.langchain.com/contact-sales?ref=blog.langchain.com) (Enterprise).
*   **Hybrid:** SaaS control plane with self-hosted data plane — ideal for teams with sensitive data but still want more of a managed service. Available only on the Enterprise plan.To get started, [contact sales](https://www.langchain.com/contact-sales?ref=blog.langchain.com)
*   **Fully Self-Hosted:** Run the entire platform within your own infrastructure. No data leaves your VPC. Available on the Enterprise plan. To get started, [contact sales](https://www.langchain.com/contact-sales?ref=blog.langchain.com).

If you want to try out a basic version of our LangGraph server in your environment, you can also self-host on our Developer plan and get up to 100k nodes executed per month for free – great to give you exposure to LangGraph Platform and run hobbyist projects on your infra. To get started on the Developer tier, [read the docs.](https://langchain-ai.github.io/langgraph/cloud/deployment/standalone_container/?ref=blog.langchain.com)

Learn more about deployment options [here](https://langchain-ai.github.io/langgraph/concepts/deployment_options/?ref=blog.langchain.com#related) and view [pricing details](http://www.langchain.com/pricing-langgraph-platform?ref=blog.langchain.com).

* * *

LangGraph Platform is the easiest way to develop, deploy, and manage long-running, stateful agents. It can be used independently from LangChain’s other products – [LangChain](https://www.langchain.com/langchain?ref=blog.langchain.com) (integrations), [LangGraph](https://www.langchain.com/langgraph?ref=blog.langchain.com) (agent orchestration), and [LangSmith](https://www.langchain.com/langsmith?ref=blog.langchain.com) (Evals and Observability), or stack together to provide an easy transition from the build phase to production.

To learn more, visit the [LangGraph Platform webpage](http://www.langchain.com/langgraph-platform?ref=blog.langchain.com). We can’t wait to see how far you can run with your agents.

### Join our newsletter

Updates from the LangChain team and community

Enter your email

Processing your application...

Success! Please check your inbox and click the link to confirm your subscription.

Sorry, something went wrong. Please try again.
