# ChatgptREST Call Evidence Boundary Prompting v1

Date: 2026-04-30

## Context

The `chatgptrest-call` skill previously told agents to include this fixed phrase for ChatGPT Pro internal technical judgment / architecture-review asks:

`不要使用网页搜索，不要切到 deep research，只基于附件和常识判断`

That was too broad. It was originally meant to prevent local repo/runtime closure reviews from spending the entire Pro turn on browser/tool work before emitting a final answer. However, making it the default harms tasks that explicitly need current external evidence, tool selection, benchmark comparison, or market/current-source validation.

## Change

Updated `skills-src/chatgptrest-call/SKILL.md` so the rule is evidence-boundary based:

- attach compact local context when local facts matter;
- state the intended evidence boundary explicitly;
- do not add blanket "no web search / no Deep Research" restrictions by default;
- use attachment-only review only when the user or task explicitly wants local-evidence judgment;
- allow current external research for tool selection, benchmark comparison, or time-sensitive facts.

The legacy examples were also softened so they no longer teach agents to include default "do not search / do not Deep Research" phrasing.

## Intended Behavior

Agents should now choose among these patterns:

- **Local closure / gate / code snapshot review**: ask Pro to prioritize attachments and mark missing evidence instead of inventing.
- **Tool selection / current benchmark / provider comparison**: allow or request external/current research as needed.
- **Deep Research**: use it only when explicitly requested or when the task genuinely requires cited current-source research.

This preserves the original goal, reducing low-value browser/tool churn for local reviews, without blocking high-value external research tasks.
