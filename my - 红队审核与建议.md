---
title: "my - 红队审核与建议"
source: "https://chatgpt.com/g/g-p-69463ae4056481919050c99739eed58c/c/69ec7ff5-9574-83e8-b7bc-b35743098b22"
author:
published:
created: 2026-04-25
description: "ChatGPT is your AI chatbot for everyday use. Chat with the most advanced AI to explore ideas, solve problems, and learn faster."
tags:
  - "clippings"
---
my - 网站升级与AI营销方案.md

File

你来做paperclip方案的红队审核意见和你的独立思考的补充建议

我会把它当成给老板/团队推进前的董事会级红队审查：先检验 Paperclip 的真实边界、落地与合规风险、Demo 稳定性和商业可信度，再给出更稳、更有展示效果的补强或重构建议。

我的初步判断会更保守：方向值得做，但应把它从全自动产品创新叙事收缩为控制台/治理中枢，并明确区分舞台展示价值、治理价值和真实执行能力。

我会按源码审计、架构边界、安全风险、可扩展点和 Labebe Demo 落地来重新红队审核 Paperclip，不只复述文档。重点会覆盖运行机制、Adapter/Skill/Issue/Governance、安装配置演示和二次开发改造建议。

我还会特别核对 API/CLI、server/UI、approvals、budgets、heartbeat、数据库与权限模型，区分真实可运行能力、展示层能力和必须沙盒隔离的部分。

## 重新结论：Paperclip 可以用，但方案必须重构成“控制平面 + 沙盒执行 + 展示前端”的三层系统

我这次不再把 Paperclip 只当成一个“能装起来的 Agent 看板”来讲。按 GitHub 源码、官方文档、issues、安全通告和你前面 Labebe 方案的目标综合看，我的判断是：

> **Paperclip 最适合成为 Labebe AI Design Studio 的“AI 团队操作系统”：管组织、任务、审批、预算、心跳、日志、责任链。**  
> **它不应该直接承担生图、CAD、爬虫、视频、真实投放、真实账号操作。**

正确架构应该是：

```markdown
Paperclip Control Plane
  管 company / agents / issues / approvals / budgets / heartbeats / logs

Labebe Demo Engine
  管真实数据、假设数据、脚本、评分、输出文件、Demo 资产

Creative Execution Services
  管生图、视频、CAD 方向图、竞品样本分析、网页生成

Labebe AI Design Studio Frontend
  管世界级视觉展示：机会雷达、Agent War Room、草图迭代、玩具厨房定制器、资产矩阵

Human Board
  管审批、风险、发布、工程确认、老板拍板
```

你上传的 Labebe 网站与 AI 营销方案核心目标，本来就不是“做一个漂亮页面”，而是把网站、素材生产、AI 工作流、审批、数据复盘串成增长链路。  
另一份调研里也反复提醒：现在最大风险不是方向错，而是“假设数字、污染数据、未验证 ROI”进入董事会材料，必须有 `truth_base_frozen.csv` 、 `DATA_TRUTH.md` 、Fact / Estimate / Hypothesis 分层。[Response: AI技术深度调研](https://chatgpt.com/g/g-p-69463ae4056481919050c99739eed58c/c/69e9e6d6-c278-83aa-81a8-532da6f2a1ba?messageId=b2fc96e9-a3e4-494d-a0a3-81d6b374ec5a&conversation_save=1)

所以我的新版方案一句话是：

> **不要把 Paperclip 做成“万能 AI 执行平台”；要把它做成 Labebe AI Design Studio 的治理层、审计层和老板演示中枢。真正的创意生成、数据分析、CAD 方向图和短视频资产，由受控脚本与外部服务执行。**

---

## 1\. 我这次实际读到的 Paperclip 关键代码与资料

我不能直接进入你本机已经 clone 的目录，也不能假装已经在你本机完成安装配置。下面的判断基于公开 GitHub 代码、官方文档、issues、安全 advisories 和关键源码路径。重点审了这些层：

```markdown
README / PRODUCT / SPEC-implementation
package.json / pnpm-workspace.yaml
server / ui / cli / packages / adapters / plugins / skills 的 monorepo 结构
agents schema
heartbeat service
adapter registry
process adapter
HTTP adapter
secret/env 解析逻辑
task / issue / checkout 机制
budget / approval / activity log 文档
security advisories
community issues around approvals, browser access, sandbox loops
```

Paperclip 官方 README 和 PRODUCT 文档明确说，它是一个 control plane，不是 chatbot、不是 workflow builder、不是 prompt manager、也不是单 agent 工具；它负责 company、agents、adapter mode、task hierarchy、heartbeats、budget、governance 等。 [GitHub+1](https://raw.githubusercontent.com/paperclipai/paperclip/master/README.md)

这点非常关键。 **Paperclip 的源码气质不是“帮你生成设计图”，而是“帮你管理一群会生成东西的 agent”。**

---

## 2\. 源码级核心发现

## 2.1 Paperclip 的底层设计是“公司治理模型”，不是普通工作流引擎

从 README、PRODUCT、SPEC 看，Paperclip 的基本抽象是：

```markdown
Company
Agent
Org Chart
Goal
Issue / Task
Heartbeat
Approval
Budget
Activity Log
Adapter
Workspace
Secret
```

V1 实现里有非常明确的取舍：单 human board operator、内置 process/http adapters、本地/认证模式、budget hard limit、atomic checkout、单 assignee、tasks/comments-only。 [GitHub](https://raw.githubusercontent.com/paperclipai/paperclip/master/doc/SPEC-implementation.md)

这说明它更像：

```markdown
AI 公司操作系统
```

不是：

```markdown
Zapier / Make / n8n 式 workflow builder
LangGraph 式强类型 pipeline runtime
ComfyUI 式图像工作流
CAD / 3D / 生图平台
```

**对 Labebe 的启发：Paperclip 适合放在“老板演示的组织层”，不要把所有设计执行都塞给它。**

---

## 2.2 Agent 数据模型是够用的，但要小心权限与 adapterConfig

源码里的 `agents` schema 包括：

```markdown
companyId
name
role
status
reportsTo
capabilities
adapterType
adapterConfig
runtimeConfig
defaultEnvironmentId
budget
spent
pauseReason
permissions
lastHeartbeatAt
metadata
```

这说明 Paperclip 对 agent 的建模很完整：角色、汇报线、预算、adapter、权限、运行状态都有。 [GitHub](https://github.com/paperclipai/paperclip/blob/master/packages/db/src/schema/agents.ts)

但红队角度也要看到： `adapterConfig` 是高风险字段，因为它决定 agent 怎么执行。官方安全通告里就有一个任意文件读取漏洞，原因是 agent-controlled `adapterConfig.instructionsFilePath` 被服务端直接读取，受影响版本 `<= v0.3.1` ，patched version 是 `2026.416.0` 。 [GitHub](https://github.com/paperclipai/paperclip/security/advisories/GHSA-3pw3-v88x-xj24)

所以我的建议是：

```markdown
Labebe Demo 里不要让普通 agent 自己改 adapterConfig。
所有 adapterConfig 由你手动配置。
所有 agent 只在固定 workspace 里运行。
不要给 agent 写权限去改自身运行配置。
```

---

## 2.3 Heartbeat 是 Paperclip 真正的“执行循环”

Paperclip 不是一直让 agent 无限跑，而是用 heartbeat 作为离散执行单元。官方文档解释得很清楚：heartbeat run 会生成上下文、调用 adapter、记录 run、处理输出、更新成本与状态；它的好处是有边界、可预算、可审计，不容易变成不可控长循环。 [Paperclip+1](https://paperclipai-paperclip.mintlify.app/concepts/heartbeats)

源码里 heartbeat 服务很重：它处理 adapter config、secrets、workspace、budget、log streaming、retry、session、payload 限制、local adapters 等。 [GitHub+1](https://github.com/paperclipai/paperclip/blob/master/server/src/services/heartbeat.ts)

这对 Labebe Demo 是好事，因为你可以展示：

```markdown
Agent wakeup
Agent reads assigned issue
Agent comments progress
Agent moves task to in_review
Board approves
Agent continues next issue
```

但它也意味着：

```markdown
不要期待 Paperclip 现场实时稳定生成所有图片、视频、CAD。
Heartbeat 更适合跑“任务推进”和“输出文件回写”，不适合作为现场实时创意工具。
```

世界级 Demo 要用：

```markdown
主路径：预生成资产 + Paperclip 记录过程
副路径：现场触发一个小任务做 live proof
兜底：所有关键展示都有 fallback 截图 / 视频
```

---

## 2.4 Issue / Task 机制是 Paperclip 最适合 Labebe 的部分

Paperclip 的 issue 是基本工作单元，支持状态、parent/child、checkout、comment、attachment。官方文档明确说 atomic checkout 防止多个 agent 同时抢同一个任务，状态从 backlog/todo/in\_progress/in\_review/done/blocked/cancelled 流转。 [Paperclip+1](https://paperclipai-paperclip.mintlify.app/guides/task-management)

这正好适合 Labebe 的 AI 设计流程：

```markdown
Company Goal
  └── Product Opportunity Radar
        ├── VOC pain clustering
        ├── competitor white-space
        ├── design opportunity brief
        ├── design director review
        ├── DFM / safety preflight
        └── concept-to-market asset matrix
```

这比“一个 agent 给一大段回答”高级很多。老板看到的是：

```markdown
AI 不是在聊天；
AI 在按组织、任务、责任、审批推进工作。
```

---

## 2.5 Process Adapter 很强，但也是最大本地风险点

Process adapter 的执行机制是 spawn 本地命令，带 cwd/env，支持 timeout、日志、取消等。官方文档写明会解析 cwd、instructions、env、session，然后 `spawn(command,args,{cwd,env})` 执行。 [Paperclip](https://paperclipai-paperclip.mintlify.app/agents/process-adapter)

这对 Labebe 很有用：

```markdown
跑 Python 评论聚类
跑 JSON 生成
跑 Markdown 报告
跑静态资产矩阵
跑 front-end build
跑 screenshot capture
```

但它的风险也非常明显：

```markdown
如果 Paperclip 暴露到公网，process adapter 等于远程代码执行入口。
如果 agent 拿到真实环境变量，可能泄露账号和 secrets。
如果 cwd 指向你的主项目或 home 目录，agent 可能读写不该碰的文件。
```

GitHub security 页面在 2026-04-16 列出了多条 High / Critical advisory，包括 OS command injection、cross-tenant token、Gmail 继承权限、未认证 API 访问等。 [GitHub](https://github.com/paperclipai/paperclip/security)

所以 Labebe Demo 第一版只能这样跑：

```markdown
local only
127.0.0.1 only
sandbox workspace only
no real Gmail
no real Shopify
no real Amazon Ads
no real Meta/TikTok Ads
no production API write token
no unrestricted shell
no public exposure
```

---

## 2.6 HTTP Adapter 是接生图、CAD、视频、爬虫服务的正确方式

Paperclip 的 HTTP adapter 会把 runId、agentId、companyId、task/issue、wakeReason、context 等发给外部 webhook；支持同步返回，也支持异步 `202 Accepted` 后 callback。 [Paperclip](https://paperclipai-paperclip.mintlify.app/agents/http-adapter)

这就是 Labebe Demo 应该用的模式：

```markdown
Paperclip 负责发任务：
“为 SpaceSmart Learning Tower 生成概念图方向”

HTTP Service 负责执行：
调用生图 / 视频 / CAD / 数据服务

HTTP Service 回写：
图片路径、prompt、报告、状态、成本、风险
```

不要让 Paperclip 自己变成生图工具。正确是：

```markdown
Paperclip = 控制台
FastAPI / Node service = 执行器
Image / CAD / Video providers = 专业工具
```

---

## 2.7 Secrets 系统有设计，但当前阶段不能完全信任

源码里的 secrets 逻辑做了敏感 key 校验、redacted placeholder 拒绝、secret\_ref 解析、company 范围验证等。 [GitHub+1](https://github.com/paperclipai/paperclip/blob/master/server/src/services/secrets.ts)

这说明 Paperclip 在设计上知道 secrets 是高风险区。但安全 advisories 也说明，目前项目还在快速演进，边界并不成熟。例如未认证 API 访问 advisory 提到多个端点可能泄露 skills、internal API structure、deployment mode、version 等。 [GitHub](https://github.com/paperclipai/paperclip/security/advisories/GHSA-xfqj-r5qw-8g4j)

我的结论：

```markdown
Demo 阶段不要把真实商业 token 放进 Paperclip。
必须用 fake token、read-only token、demo token 或本地 mock service。
需要真实外部服务时，也只给最小权限、短期 token、单独账号。
```

---

## 2.8 Budget 功能适合老板演示，但不要误解 task-level enforcement

Paperclip 文档说明，它能追踪 agent token spend，并在 agent/company 超预算时 auto-pause；但 task-level 目前主要是 tracking，不是 V1 enforced hard stop。 [Paperclip](https://paperclipai-paperclip.mintlify.app/guides/cost-budgets)

所以 Demo 可以展示：

```markdown
Company budget: $50 demo cap
CEO budget: $15
VOC budget: $8
Design Director budget: $8
DFM/Safety budget: $5
GTM budget: $5
```

但不要对老板说：

```markdown
每个具体设计任务都会被系统级强制预算中断。
```

更准确说：

```markdown
Paperclip 能在 company / agent 层面强制预算。
task 成本可以追踪；task-level 强制预算需要我们在 Labebe Demo Engine 里额外做 gate。
```

---

## 2.9 Approval 系统能用，但现在还不是强制动作级护栏

官方 approvals 文档支持 agent hire 和 CEO strategy；CEO strategy 在未批准前不能推进到 in\_progress 或 delegate。 [Paperclip+1](https://paperclipai-paperclip.mintlify.app/guides/governance-approvals)

但社区 issue 也指出，外部高风险动作的 action-class guard 目前缺少平台级强制执行，很多情况下仍依赖 prompt 让 agent 主动请求 approval。 [GitHub](https://github.com/paperclipai/paperclip/issues/3017)  
另一个 issue 也提到 pipeline-step approval / interrupt points 仍是待增强方向。 [GitHub](https://github.com/paperclipai/paperclip/issues/762)

这对 Labebe 很重要。你不能只靠：

```markdown
Prompt 里写：发布前要审批
```

你要在 Demo 里额外做硬规则：

```markdown
任何发布、真实外部请求、CAD production claim、安全认证 claim、价格/ROI claim，都不能由 agent 直接执行。
必须生成 Human Review Issue。
必须由人把 review issue 标记为 done。
父任务才能继续。
```

这叫：

```markdown
Issue-based approval workaround
```

也就是用 Paperclip 的 task tree 和人工状态流转弥补 action guard 不成熟。

---

## 2.10 Browser / 真实网页操作暂时不适合做主线

社区 issue 已经有人提出 browser access approval system：read\_only、interactive、transactional 三档授权，按 task 过期，PreToolUse hook 审计等。 [GitHub](https://github.com/paperclipai/paperclip/issues/2390)

这说明真实浏览器操作、登录外部网站、填表、点击、提交，这些都还不是 Paperclip 的强安全默认能力。

所以 Labebe 第一版不要让 agent 直接：

```markdown
登录 Amazon Seller
登录 Shopify Admin
登录 Meta Ads
登录 TikTok Ads
登录 Gmail
登录 Pinterest
登录爬虫平台
```

第一版应该用：

```markdown
手动导出的 CSV
手动保存的竞品截图
公开网页样本
本地 JSON
本地图片
mock API
```

---

## 2.11 本地 agent 可能出现 sandbox / approval loop，必须用 wrapper

社区 issue 里有人提到，agent 在 heartbeat 里尝试读取环境变量、curl API、写文件时被安全系统阻断，然后进入“panic loop”，不断尝试奇怪 workaround，消耗 token。 [GitHub](https://github.com/paperclipai/paperclip/issues/447)

这对配置很实际。不要让 Claude/Codex agent 自由用 shell。应该给每类任务一个 wrapper：

```markdown
python scripts/paperclip_runner.py --role voc --task-id $PAPERCLIP_TASK_ID
python scripts/paperclip_runner.py --role design_director --task-id $PAPERCLIP_TASK_ID
python scripts/paperclip_runner.py --role dfm --task-id $PAPERCLIP_TASK_ID
```

Agent prompt 里写死：

```markdown
不要直接 bash。
不要 curl。
不要读系统环境。
只调用 scripts/paperclip_runner.py。
只读 /data、/docs。
只写 /outputs。
```

这会显著提高稳定性。

---

## 3\. 新版系统架构：Paperclip 只做“AI 设计公司控制台”

我建议把项目改名为：

```markdown
Labebe AI Design Office OS
powered by Paperclip
```

核心架构如下：

```markdown
labebe-ai-design-studio/
│
├── paperclip/
│   └── Paperclip local instance
│       ├── Company: Labebe AI Design Studio
│       ├── Agents
│       ├── Issues
│       ├── Approvals
│       ├── Budgets
│       └── Activity Log
│
├── workspace/
│   ├── docs/
│   │   ├── DESIGN.md
│   │   ├── DATA_TRUTH.md
│   │   ├── AGENTS.md
│   │   ├── FORBIDDEN_CLAIMS.md
│   │   ├── ACTION_POLICY.md
│   │   └── REFERENCE_MAP.md
│   │
│   ├── data/
│   │   ├── products_seed.json
│   │   ├── review_signal_samples.csv
│   │   ├── competitor_samples.csv
│   │   ├── trend_samples.csv
│   │   └── truth_base_frozen.csv
│   │
│   ├── scripts/
│   │   ├── paperclip_runner.py
│   │   ├── voc_to_design.py
│   │   ├── opportunity_radar.py
│   │   ├── design_director_score.py
│   │   ├── dfm_safety_preflight.py
│   │   ├── concept_to_market_matrix.py
│   │   └── render_demo_outputs.py
│   │
│   ├── outputs/
│   │   ├── opportunity_radar.md
│   │   ├── spacesmart_learning_tower_brief.md
│   │   ├── design_scorecard.md
│   │   ├── dfm_safety_preflight.md
│   │   ├── asset_matrix.md
│   │   └── boss_demo_script.md
│   │
│   └── assets/
│       ├── product_images/
│       ├── concept_images/
│       ├── video_posters/
│       └── demo_screenshots/
│
├── services/
│   ├── design-render-service/
│   ├── cad-direction-service/
│   ├── competitor-sample-service/
│   └── video-storyboard-service/
│
└── frontend/
    └── labebe-ai-design-studio-demo/
        ├── Opportunity Radar
        ├── Agent War Room
        ├── Sketch-to-Concept
        ├── Custom Toy Kitchen Builder
        ├── Design Director Scorecard
        ├── DFM / Safety Preflight
        └── Concept-to-Market Asset Matrix
```

这套结构比“把 Paperclip 当一个大工具”稳很多。

---

## 4\. Agent Team 重新设计：少而强，不要 20 个 agent

第一版最多 9 个 agent。

| Agent | 定位 | Adapter | 任务 |
| --- | --- | --- | --- |
| Product Innovation Director | CEO / 总控 | Claude/Codex local | 拆任务、汇总、请求审批 |
| Data Truth Guard | 数据真实性守门 | process + LLM | 检查价格、review、claim、假设 |
| VOC Intelligence Analyst | 用户反馈分析 | process + LLM | 评论/退货/客服痛点转设计要求 |
| Competitive Radar Analyst | 竞品白区 | HTTP/process | 竞品矩阵、价格带、功能缺口 |
| Design Strategy Agent | 产品设计策略 | Claude/Codex local | 机会转 brief |
| Design Director Agent | 审美总监 | Claude/Codex local | 品牌匹配、风格评分、改 prompt |
| DFM & Safety Preflight Agent | 工程/安全初审 | Claude/Codex + script | 风险、BOM、结构、claim 预警 |
| Concept-to-Market Agent | 上市测试资产 | Claude/Codex + script | PDP、A+、TikTok、Meta、Email |
| Demo Producer Agent | 展示导演 | process + LLM | 90 秒短视频、15 分钟老板路线 |

不要第一版做：

```markdown
CEO / COO / CFO / CTO / CMO / Legal / HR / Social / Amazon / TikTok / Google / CAD / Video / Designer / Engineer / QA / Analyst...
```

太多 agent 会让 Demo 变成“组织图很热闹，产物很稀薄”。

---

## 5\. Paperclip 里应该建立的 Issue Tree

这是新版 Demo 的骨架。

```markdown
Company Goal:
Build a board-ready Labebe AI Design Studio demo that turns customer, competitor and product signals into review-ready product design concepts and launch-test assets.

EPIC 0 — CEO Strategy Approval
  0.1 Draft Labebe AI Design Studio strategy
  0.2 Define agent roles and approval gates
  0.3 Submit CEO strategy for board approval

EPIC 1 — Data Truth Foundation
  1.1 Create DATA_TRUTH.md
  1.2 Create truth_base_frozen.csv
  1.3 Label demo samples vs facts
  1.4 Build forbidden claims list

EPIC 2 — Product Opportunity Radar
  2.1 Import Labebe products seed
  2.2 Summarize review signals
  2.3 Build competitor feature matrix
  2.4 Score opportunity clusters
  2.5 Recommend top 3 design opportunities

EPIC 3 — VOC to Product Concept
  3.1 Cluster Learning Tower pain points
  3.2 Translate pain points into design requirements
  3.3 Create SpaceSmart Foldable Learning Tower brief
  3.4 Request product opportunity approval

EPIC 4 — Sketch-to-Concept Lab
  4.1 Define sketch input format
  4.2 Generate 4 concept routes
  4.3 Create concept image prompts
  4.4 Score brand fit
  4.5 Select one direction for review

EPIC 5 — Custom Toy Kitchen Builder
  5.1 Define toy kitchen module schema
  5.2 Map Labebe pretend-play SKUs to modules
  5.3 Generate Mini Bakery Kitchen Corner sample
  5.4 Create waitlist / PDP mock

EPIC 6 — Design Director Review
  6.1 Score SpaceSmart Learning Tower
  6.2 Score Mini Bakery Kitchen Corner
  6.3 Generate next-iteration prompts
  6.4 Flag off-brand risks

EPIC 7 — DFM / Safety / Cost Preflight
  7.1 Identify tipping / pinch / small-part risks
  7.2 Generate engineering questions
  7.3 Create preliminary BOM assumptions
  7.4 Mark human engineering review required

EPIC 8 — Concept-to-Market Asset Matrix
  8.1 Generate PDP module
  8.2 Generate Amazon A+ outline
  8.3 Generate TikTok 15s scripts
  8.4 Generate Meta carousel outline
  8.5 Generate Google image brief
  8.6 Generate email / waitlist block

EPIC 9 — Boss Demo Production
  9.1 Record Paperclip dashboard
  9.2 Record Agent War Room
  9.3 Record Custom Toy Kitchen Builder
  9.4 Cut 90-second short video
  9.5 Prepare 15-minute boss presentation
```

每个 parent issue 都要 trace back to company goal。Paperclip 的 task hierarchy 和 atomic checkout 正好适合这个。 [Paperclip+1](https://paperclipai-paperclip.mintlify.app/guides/task-management)

---

## 6\. 安装与配置：我建议的安全启动方式

## 6.1 先确认版本和依赖

Paperclip 官方本地部署要求 Node.js 20+、pnpm 9.15+，本地模式默认 embedded PostgreSQL，服务在 `localhost:3100` 。 [Paperclip](https://paperclipai-paperclip.mintlify.app/deployment/local)

```markdown
cd /path/to/paperclip

node -v
pnpm -v

corepack enable
corepack prepare pnpm@9.15.4 --activate
```

## 6.2 用源码启动，不要先上公网

```markdown
cd /path/to/paperclip

git pull

pnpm install
pnpm typecheck
pnpm test
```

启动 Labebe 专用实例：

```markdown
export PAPERCLIP_HOME="$PWD/.paperclip-labebe"
export PAPERCLIP_INSTANCE_ID="labebe"
export PAPERCLIP_TELEMETRY_DISABLED=1
export HOST="127.0.0.1"
export PORT="3100"

pnpm paperclipai run
```

健康检查：

```markdown
curl http://127.0.0.1:3100/api/health
curl http://127.0.0.1:3100/api/companies
```

官方文档也给了 `/api/health` 和 `/api/companies` 作为本地验证方式。 [Paperclip](https://paperclipai-paperclip.mintlify.app/deployment/local)

## 6.3 不建议第一天用 authenticated/public

官方本地开发文档说明 local trusted 默认无登录、绑定 `127.0.0.1` ，适合本地实验；远程私有访问可以考虑 Tailscale/private 模式。 [Paperclip](https://paperclipai-paperclip.mintlify.app/deployment/local)

我的建议：

```markdown
本地演示：local_trusted + 127.0.0.1
远程给团队看：Tailscale / VPN / SSH tunnel
不要 public
不要 open signup
不要把 3100 暴露公网
```

这不是保守，是必须。安全 advisory 已经证明，Paperclip 近期存在过 authenticated mode 默认配置下未认证 RCE 风险，impact 包括服务器用户权限下的命令执行、文件系统访问、数据库访问、内网 pivot 等。 [GitHub](https://github.com/paperclipai/paperclip/security/advisories/GHSA-68qg-g8mg-6pr7)

---

## 7\. 安全红队清单：必须这样配

```markdown
[ ] 使用最新 patched version，不要跑旧 v0.3.1 或 2026.403.0 一类历史风险版本
[ ] HOST=127.0.0.1
[ ] 不开放公网端口
[ ] 不接真实 Gmail
[ ] 不接真实 Shopify Admin write token
[ ] 不接真实 Amazon Seller / Ads write token
[ ] 不接真实 Meta / TikTok Ads token
[ ] 不把 ~/.ssh、~/.aws、~/Documents 暴露给 agent cwd
[ ] Paperclip 使用独立 OS user
[ ] workspace 使用独立目录
[ ] 所有 process adapter command 只指向 wrapper script
[ ] 禁止 agent 修改 adapterConfig
[ ] 禁止 unreviewed import company / skills
[ ] 禁止从未知 repoUrl 自动 clone
[ ] 所有外部服务只用 demo key
[ ] 所有真实客户数据脱敏
[ ] outputs 里所有数字标 Fact / Estimate / Hypothesis / Demo Sample
```

尤其注意两个点：

第一，process adapter 是强执行能力，所以必须隔离。  
第二，Paperclip GitHub security 页面已经列出多个安全 advisory，不要把它当成熟企业级多租户 SaaS 直接公网部署。 [GitHub](https://github.com/paperclipai/paperclip/security)

---

## 8\. Adapter 配置方案

## 8.1 CEO / Design Strategy / Design Director

用 Claude Local 或 Codex Local。它们负责：

```markdown
策略
拆解
综合判断
文案
设计审查
任务总结
```

但它们不直接：

```markdown
爬虫
生图
CAD
发邮件
改 Shopify
发布广告
```

## 8.2 Process Adapter：只跑受控脚本

示例 config：

```markdown
{
  "adapterType": "process",
  "adapterConfig": {
    "command": "python3",
    "args": [
      "scripts/paperclip_runner.py",
      "--role",
      "voc"
    ],
    "cwd": "/absolute/path/to/labebe-ai-design-studio/workspace",
    "timeoutSec": 300
  }
}
```

`paperclip_runner.py` 根据 `PAPERCLIP_TASK_ID` 读取任务，只读 `docs/` 和 `data/` ，只写 `outputs/` 。

## 8.3 HTTP Adapter：接生图 / CAD / 视频 / 竞品样本服务

示例：

```markdown
{
  "adapterType": "http",
  "adapterConfig": {
    "url": "http://127.0.0.1:8787/paperclip/run",
    "method": "POST",
    "timeoutMs": 600000,
    "headers": {
      "Authorization": "Bearer ${secrets.labebe_demo_service_key}"
    }
  }
}
```

HTTP service 返回：

```markdown
{
  "status": "success",
  "summary": "Generated concept-to-market asset matrix",
  "artifacts": [
    "outputs/asset_matrix.md",
    "assets/concept_images/spacesmart_v1.png"
  ],
  "usage": {
    "costUsd": 0.42
  }
}
```

这样 Paperclip 记录任务、预算和日志，外部服务做真正执行。HTTP adapter 的 sync/async/callback 模式正好支持这个。 [Paperclip](https://paperclipai-paperclip.mintlify.app/agents/http-adapter)

---

## 9\. 必须创建的项目文件

第一批不要先写代码，先建治理文件。

```markdown
docs/DESIGN.md
docs/DATA_TRUTH.md
docs/AGENTS.md
docs/FORBIDDEN_CLAIMS.md
docs/ACTION_POLICY.md
docs/REFERENCE_MAP.md
docs/DEMO_SAMPLE_POLICY.md
docs/BOSS_TALK_TRACK.md
```

## DATA\_TRUTH.md 必须写死

```markdown
# DATA_TRUTH.md

## Hard facts currently allowed

- Labebe scraped product count: 46
- Category distribution:
  - furniture: 17
  - rockers-ride-ons: 13
  - pretend-play: 9
  - activity-educational-toys: 6
  - new-in: 1
- Pink Unicorn Plush Rocker: $109.99 / 18 reviews
- Cream Wooden Play Kitchen: $129.99 / 9 reviews
- Natural Wood Montessori Shelf: $114.99 / 9 reviews

## Never invent

- sales
- revenue
- review count
- rating
- ROI
- ACoS
- patents
- certifications
- awards
- customer quotes
- manufacturing origin
- safety compliance
- production CAD readiness

## Labels

Fact:
Estimate:
Hypothesis:
Demo Sample:
To Confirm:
```

## ACTION\_POLICY.md 必须写死

```markdown
# ACTION_POLICY.md

Agents may generate drafts.

Agents may not:
- send emails
- publish ads
- modify Shopify
- change product price
- create production CAD claims
- claim safety certification
- access real customer data
- approve product launch
- approve manufacturing
- commit budget externally

Every high-risk action must create a Human Review issue.
```

---

## 10\. Demo 重新设计：6 条主线

## Demo A：Design Opportunity Radar

目标：证明 AI 能从数据中找设计机会。

输入：

```markdown
products_seed.json
review_signal_samples.csv
competitor_samples.csv
trend_samples.csv
DATA_TRUTH.md
```

输出：

```markdown
P0 — SpaceSmart Foldable Learning Tower
P0 — Modular Tiny Pretend Kitchen
P0 — Giftable Animal Rocker Collection
P1 — Playroom Reset System
P1 — Assembly Experience Optimizer
```

Paperclip 展示：

```markdown
VOC Agent 完成 pain cluster
Competitive Agent 完成 white space
Design Strategy Agent 完成 opportunity brief
CEO 请求 approval
```

## Demo B：VOC → 新品概念

目标：展示“评论反馈变设计方向”。

以 Learning Tower 为例：

```markdown
Pain:
- takes too much kitchen space
- assembly is confusing
- parents want stability
- hard to clean
- kids outgrow quickly

Concept:
SpaceSmart Foldable Learning Tower

Features:
- fold-flat storage
- wider anti-tip base
- rounded safety rails
- wipe-clean surface
- adjustable platform
```

输出：

```markdown
spacesmart_learning_tower_brief.md
design_requirements.json
concept_prompt_pack.md
```

## Demo C：Sketch-to-Concept

目标：补足企业美学创意不足。

流程：

```markdown
粗草图 / 一句话
  ↓
4 条风格路线
  ↓
每条 3 个概念 prompt
  ↓
Design Director score
  ↓
DFM risk
  ↓
下一轮 prompt
```

风格路线：

```markdown
Montessori Minimal
Small-Space Foldable
Soft Giftable Pastel
Outdoor Garden Play
```

## Demo D：Custom Toy Kitchen Builder

目标：最强消费者视觉 Demo。

输入：

```markdown
Child age: 4
Room size: small playroom
Style: Cream Montessori
Favorite play: baking + coffee shop
Budget: medium
```

输出：

```markdown
Mini Bakery Kitchen Corner
- oven
- sink
- bakery shelf
- coffee bar
- storage bins
- recommended dimensions
- recommended Labebe SKUs
- waitlist block
- concept image prompt
```

这条不说“生产 CAD 已完成”，只说：

```markdown
AI-generated concept direction, ready for design and engineering review.
```

## Demo E：Design Director + DFM / Safety Preflight

目标：让老板相信 AI 不是只会画图。

输出：

```markdown
Brand Fit: 86
Parent Taste: 82
Montessori Calmness: 88
Giftability: 74
Manufacturing Realism: 61

Risk flags:
- hinge pinch point
- tipping risk
- assembly screw count
- packaging volume
- cleanability
```

明确写：

```markdown
Preflight only. Human engineering validation required.
```

## Demo F：Concept-to-Market Asset Matrix

目标：把产品设计接到增长。

一个概念输出：

```markdown
PDP hero
PDP benefit blocks
Amazon A+ outline
TikTok 15s script
Meta carousel
Google Shopping lifestyle brief
Email waitlist block
Boss approval memo
```

这对应你原始网站升级方案里的核心方向：一个 SKU 或一个概念要能裂变成 Amazon、TikTok、Meta、Google、独立站多渠道资产。

---

## 11\. Paperclip 里的演示画面怎么拍

世界级 Demo 不应该只拍前端，也要拍 Paperclip 的“组织治理感”。

## 画面 1：Company Goal

```markdown
Labebe AI Design Studio
Goal:
Turn customer signals, competitor gaps and Labebe design rules into review-ready product concepts and launch-test assets.
```

## 画面 2：Org Chart

```markdown
Product Innovation Director
├── Data Truth Guard
├── VOC Intelligence Analyst
├── Competitive Radar Analyst
├── Design Strategy Agent
├── Design Director Agent
├── DFM & Safety Preflight Agent
├── Concept-to-Market Agent
└── Demo Producer Agent
```

## 画面 3：Issue Tree

展示：

```markdown
EPIC 2 — Product Opportunity Radar
EPIC 3 — VOC to Product Concept
EPIC 5 — Custom Toy Kitchen Builder
EPIC 7 — DFM / Safety / Cost Preflight
```

## 画面 4：Heartbeat

展示 agent 被唤醒、执行、写 comment、进入 in\_review。

## 画面 5：Approval

展示：

```markdown
CEO Strategy Approval
Product Opportunity Approval
Design Concept Human Review
DFM / Safety Human Review
```

## 画面 6：Budget

展示：

```markdown
Company cap: $50
Agent spend
Budget warning
```

## 画面 7：Activity Log

展示完整轨迹：

```markdown
CEO proposed strategy
Board approved
VOC completed analysis
Design Director requested revision
DFM flagged pinch risk
GTM generated asset matrix
```

Paperclip 文档明确说 activity log 记录 agent 创建、issue 状态、comments、approvals、budget changes 等，非常适合老板演示审计性。 [Paperclip](https://paperclipai-paperclip.mintlify.app/)

---

## 12\. 90 秒短视频脚本重写

片名：

```markdown
Labebe AI Design Studio
From customer signals to product design.
```

## 0–8 秒：问题

画面：Labebe 摇马、Learning Tower、Play Kitchen、Montessori Shelf 快速闪过。

字幕：

```markdown
What should Labebe design next?
```

旁白：

```markdown
过去新品方向靠经验、展会和老板判断。现在，我们让 AI 从真实信号开始。
```

## 8–20 秒：Paperclip AI Team

画面：Paperclip company、org chart、agent heartbeat。

字幕：

```markdown
AI Design Agent Team
VOC · Competitor · Design · DFM · GTM
```

## 20–35 秒：机会雷达

画面：Opportunity Radar。

字幕：

```markdown
P0 Opportunity:
SpaceSmart Foldable Learning Tower
```

## 35–50 秒：VOC 到设计 brief

画面：痛点卡片变成功能要求。

字幕：

```markdown
Small kitchen pain → fold-flat design
Assembly confusion → fewer steps
Stability concern → wider base
```

## 50–65 秒：概念图与设计评分

画面：SpaceSmart Learning Tower 概念图 + Design Director score。

字幕：

```markdown
Brand Fit 86
Home Aesthetic 84
Manufacturing Realism 61
```

## 65–78 秒：DFM / Safety Preflight

画面：风险清单。

字幕：

```markdown
Preflight only.
Human engineering review required.
```

## 78–88 秒：资产矩阵

画面：PDP、Amazon A+、TikTok、Meta、Google、Email 卡片飞出。

字幕：

```markdown
One concept → multi-channel launch test assets
```

## 88–90 秒：收口

```markdown
Design smarter.
Prototype faster.
Test earlier.
```

---

## 13\. 安装后第一天怎么跑

## 上午：Paperclip 沙盒

```markdown
cd /path/to/paperclip

export PAPERCLIP_HOME="$PWD/.paperclip-labebe"
export PAPERCLIP_INSTANCE_ID="labebe"
export PAPERCLIP_TELEMETRY_DISABLED=1
export HOST="127.0.0.1"
export PORT="3100"

pnpm install
pnpm typecheck
pnpm paperclipai run
```

打开：

```markdown
http://127.0.0.1:3100
```

## 中午：建 workspace

```markdown
mkdir -p ~/labebe-ai-design-studio/workspace/{docs,data,scripts,outputs,assets}
```

创建：

```markdown
docs/DESIGN.md
docs/DATA_TRUTH.md
docs/ACTION_POLICY.md
docs/FORBIDDEN_CLAIMS.md
data/products_seed.json
data/review_signal_samples.csv
data/competitor_samples.csv
scripts/paperclip_runner.py
```

## 下午：建 Company + CEO

```markdown
Company:
Labebe AI Design Studio

Goal:
Build a board-ready AI Design Studio demo that turns customer, competitor and product signals into review-ready product concepts, design preflight notes and launch-test assets.
```

CEO prompt 重点：

```markdown
Use Paperclip issues.
Do not invent facts.
All high-risk actions require Human Review issues.
Use DATA_TRUTH.md and DESIGN.md.
Generate outputs into /outputs.
Never access real external accounts.
```

## 晚上：跑第一个任务

Issue：

```markdown
Draft Labebe AI Design Studio strategy and approval gates
```

CEO 输出：

```markdown
strategy memo
agent team
issue tree
approval gates
demo risks
90-second story
```

你 approve 之后再跑后续 agent。

---

## 14\. 第二天到第七天路线图

## Day 2：Data Truth + Opportunity Radar

交付：

```markdown
truth_base_frozen.csv
DATA_TRUTH.md
opportunity_radar.md
top_3_design_opportunities.md
```

## Day 3：VOC → SpaceSmart Learning Tower

交付：

```markdown
pain_clusters.md
spacesmart_learning_tower_brief.md
design_requirements.json
concept_prompt_pack.md
```

## Day 4：Sketch-to-Concept + Design Director

交付：

```markdown
4 style routes
12 concept prompts
design_scorecard.md
next_iteration_prompt.md
```

## Day 5：Custom Toy Kitchen Builder

交付：

```markdown
toy_kitchen_module_schema.json
mini_bakery_kitchen_corner.md
custom_kitchen_builder_frontend_mock
waitlist_block.md
```

## Day 6：DFM / Safety + Asset Matrix

交付：

```markdown
dfm_safety_preflight.md
bom_assumptions.md
concept_to_market_asset_matrix.md
tiktok_scripts.md
pdp_module.md
amazon_a_plus_outline.md
```

## Day 7：世界级展示包装

交付：

```markdown
Paperclip dashboard recording
AI Design Studio frontend recording
90-second video
15-minute boss talk track
fallback screenshots
QA checklist
```

---

## 15\. 前端 Demo 必须单独做，不要只靠 Paperclip UI

Paperclip UI 的风格是操作台，不是品牌级 Demo。老板看 Paperclip 会明白“AI 团队在工作”，但不会被视觉惊艳。

所以要做一个单独的：

```markdown
Labebe AI Design Studio Frontend
```

页面结构：

```markdown
/ai-design-studio
  Overview

/ai-design-studio/opportunity-radar
  产品机会雷达

/ai-design-studio/war-room
  Agent Team 头脑风暴

/ai-design-studio/voc-to-concept
  评论到新品概念

/ai-design-studio/sketch-to-concept
  草图到概念迭代

/ai-design-studio/custom-toy-kitchen
  家长定制玩具厨房

/ai-design-studio/design-director
  美学评分

/ai-design-studio/dfm-safety
  工程与安全初审

/ai-design-studio/asset-matrix
  概念到多渠道素材
```

视觉方向：

```markdown
前台 Consumer Site:
Warm Premium Montessori Home

后台 AI Studio:
Calm dark control room
Linear / Raycast / Stripe Atlas 风格
```

Paperclip 负责“真实工作过程”，前端负责“世界级展示效果”。

---

## 16\. 最重要的红队意见

## P0-1：不能公网部署

由于近期 security advisories 很密集，而且涉及 RCE、token、未认证访问、Gmail 权限继承等问题，第一版只能本地或 VPN/Tailscale。 [GitHub+1](https://github.com/paperclipai/paperclip/security/advisories/GHSA-68qg-g8mg-6pr7)

## P0-2：不能接真实账号

尤其是：

```markdown
Gmail
Google Calendar
Shopify Admin
Amazon Seller
Amazon Ads
Meta Ads
TikTok Ads
Drive/Dropbox
真实支付
真实采购系统
```

社区 issue 已经有 agent 因缺少 action-class guards 而在没有审批的情况下创建外部 calendar invite 的案例。 [GitHub](https://github.com/paperclipai/paperclip/issues/3017)

## P0-3：不能说 AI 生成 production CAD

只能说：

```markdown
concept render
3D direction
engineering review brief
DFM preflight
```

不能说：

```markdown
production-ready CAD
factory-ready drawing
safety-certified design
```

## P0-4：不能让 agent 自由爬取竞品

第一版使用：

```markdown
manual CSV
public screenshots
curated sample pages
third-party export
```

而不是 unrestricted crawler。

## P0-5：不能让 AI 编漂亮数字

所有价格、评论、销量、ROI、ACoS、review、认证都必须过 Data Truth Guard。你上传的调研里已经指出，旧框架里的“污染数字”会直接降低董事会安全度。[Response: AI技术深度调研](https://chatgpt.com/g/g-p-69463ae4056481919050c99739eed58c/c/69e9e6d6-c278-83aa-81a8-532da6f2a1ba?messageId=b2fc96e9-a3e4-494d-a0a3-81d6b374ec5a&conversation_save=1)

---

## 17\. 我对 Paperclip 的最终评分

```markdown
作为 Labebe AI Design Studio 控制台：9 / 10
作为老板演示中的“AI 团队治理层”：9 / 10
作为真实执行引擎：6 / 10
作为公网生产系统：3 / 10
作为本地沙盒 Demo：8 / 10
作为生图 / CAD / 视频工具：2 / 10
作为任务、预算、审批、日志系统：8.5 / 10
```

最终判断：

> **Paperclip 值得用，但必须把它放在正确位置：它是 AI 设计团队的控制平面，不是 AI 设计能力本身。**

---

## 18\. 新版一句话方案

```markdown
用 Paperclip 搭建 Labebe AI Design Studio 的组织、任务、审批、预算和审计系统；
用本地 Demo Engine 固化真实数据、脚本、评分和输出；
用 HTTP / Process adapter 调用受控生图、CAD 方向图、视频脚本和竞品样本服务；
用独立前端做世界级视觉展示；
用 Human Review issue 保证所有产品、工程、安全、发布和商业数字必须人审。
```

老板最后看到的不是：

```markdown
我们装了一个 AI 工具。
```

而是：

```markdown
Labebe 拥有了一个可管理、可审批、可追踪、可复盘的 AI 产品创新团队。
它能从评论和竞品里找方向，
从草图和数据里生成概念，
从概念里做审美、工程、安全和上市测试初审，
最后把一个新品方向变成 PDP、短视频、Amazon A+、Meta、Google、Email 和老板审批包。
```

这是 Paperclip 在这个项目里最有价值、也最安全的用法。

我会把这次当成技术选型和架构红队：先深读 LangGraph / DeepAgents 的源码骨架、执行模型、状态/中断/持久化和工具隔离，再横向比较 Paperclip、OpenAI Agents SDK、AutoGen、CrewAI、Mastra、PydanticAI、Google ADK，以及 Temporal/Inngest 这类工作流底座。

我已经看了 LangGraph 和 DeepAgents 的核心源码；初步判断是 LangGraph 适合做工作流骨架，DeepAgents 适合做强执行型员工，组合更适合 Labebe。

## 结论：LangGraph + DeepAgents 可以，而且比 Paperclip 更适合做“真实执行层”；但不要用它替代 Paperclip 的“老板控制台”

我这次的判断是：

> **最佳方案不是 Paperclip vs LangGraph DeepAgents 二选一，而是 Paperclip + LangGraph + DeepAgents 组合。**

对 Labebe 这个项目，最合适的分工是：

```markdown
Paperclip
= AI 公司控制台 / 老板演示层 / 任务、预算、审批、日志、Agent Team 组织结构

LangGraph
= 真实工作流编排层 / 状态机 / 人审中断 / 可恢复执行 / 多阶段流程

DeepAgents
= 每个复杂节点里的“长任务专家 Agent” / 文件读写 / 研究综合 / 子 Agent 分派 / 报告生成

前端 Demo
= Labebe AI Design Studio 可视化展示层

受控外部服务
= 生图、视频、CAD 方向图、竞品样本分析、数据清洗、短视频素材导出
```

一句话：

```markdown
Paperclip 管“谁在做、做到了哪、要不要审批”；
LangGraph 管“流程怎么走、状态怎么保存、哪里暂停给人审”；
DeepAgents 管“每一步复杂脑力活怎么完成”。
```

如果只选一个来做 Demo 执行层，我会选 **LangGraph + DeepAgents** 。  
如果要做老板觉得“这是一个 AI 产品创新团队”的世界级展示，我会保留 **Paperclip** 做控制台。

Labebe 的核心目标不是普通 AI 聊天，而是把评论、销量、竞品、趋势、设计 brief、草图迭代、DFM / 安全初审、短视频和多渠道素材串成一条增长链路。你之前的网站升级方案已经把 Labebe 定位为“场景化儿童成长空间品牌 + 多渠道素材中台 + AI 内容生产工作流”，并且明确了 46 个 SKU、产品类目和素材生产方向。  
另一个审计结论也反复提醒：现在最大风险不是方向错，而是“污染数字、假设 ROI、未验证数据”混入董事会材料，所以必须有 `truth_base_frozen.csv` 、 `DATA_TRUTH.md` 、Fact / Estimate / Hypothesis 分层。[Response: AI技术深度调研](https://chatgpt.com/g/g-p-69463ae4056481919050c99739eed58c/c/69e9e6d6-c278-83aa-81a8-532da6f2a1ba?messageId=b2fc96e9-a3e4-494d-a0a3-81d6b374ec5a&conversation_save=1)

所以我建议你最终做成：

```markdown
Labebe AI Design Studio
Powered by Paperclip Control Plane + LangGraph Runtime + DeepAgents Specialists
```

---

## 1\. 我对 LangGraph DeepAgents 的源码级判断

## 1.1 DeepAgents 不是“多 Agent 平台”，而是“长任务 Agent Harness”

DeepAgents 的 README 和源码都说明，它解决的是 shallow agent 不适合长复杂任务的问题。它内置四类能力：

```markdown
planning tool
filesystem
subagents
detailed prompt / context engineering
```

README 明确列出 DeepAgents 提供 `write_todos` 、文件系统工具、shell 执行、 `task` 子 Agent、上下文管理等；并且 `create_deep_agent` 返回的是一个 compiled LangGraph graph，所以它天然可以接 LangGraph 的 checkpoint、streaming、Studio 等能力。 [GitHub+1](https://github.com/langchain-ai/deepagents)

源码里的 `create_deep_agent` 更关键。它不是简单 prompt wrapper，而是按 middleware stack 组装：

```markdown
TodoListMiddleware
SkillsMiddleware
FilesystemMiddleware
SubAgentMiddleware
SummarizationMiddleware
HumanInTheLoopMiddleware
PermissionMiddleware
MemoryMiddleware
...
```

最后调用 LangChain / LangGraph 的 `create_agent` 并返回 `CompiledStateGraph` 。这说明 DeepAgents 本质是一个“带默认能力包的 LangGraph Agent Runtime”。 [GitHub](https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/deepagents/graph.py)

对 Labebe 来说，这非常适合做：

```markdown
VOC 分析专家
竞品调研专家
设计策略专家
Design Director
DFM / Safety Preflight
Concept-to-Market 资产矩阵专家
Demo Producer
```

但它不适合直接承担：

```markdown
公司组织图
老板审批台
预算看板
Agent 员工管理
多任务队列
长期公司运营
```

这些仍然是 Paperclip 更合适。

---

## 1.2 DeepAgents 的 subagents 很好用，但不是 Paperclip 那种“员工”

DeepAgents 的 `task` 工具会启动一个子 Agent，子 Agent 拿隔离上下文去完成一项复杂任务，最后把单一结果返回给主 Agent。源码说明子 Agent 可以并发启动，并且每次调用是 stateless 的；也就是说，它更像“临时专家调用”，不是持久员工。 [GitHub](https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/deepagents/middleware/subagents.py)

这点对架构很重要。

Paperclip 里的 Agent 更像：

```markdown
VOC Intelligence Analyst
Design Director
DFM Agent
GTM Agent
```

有身份、有任务、有预算、有状态、有活动记录。

DeepAgents subagent 更像：

```markdown
“帮我单独分析这 20 条 learning tower 差评”
“帮我单独生成 4 条设计路线”
“帮我单独检查这个概念有没有结构风险”
```

所以它们不是替代关系。

正确用法：

```markdown
Paperclip Agent = 可展示的团队成员
LangGraph Node = 流程阶段
DeepAgents Subagent = 阶段内部临时专家
```

---

## 1.3 DeepAgents 的文件系统和 shell 能力很强，但安全边界必须自己做硬

DeepAgents 有 filesystem backend 和 `execute` 工具。源码里 `FilesystemBackend` 对本地文件系统有直接读写能力，并且明确警告：如果用在 web server / HTTP API 场景，可能读到 secrets、环境文件、项目代码，甚至在结合网络工具时造成数据外泄； `virtual_mode=False` 时绝对路径和 `..` 还可能逃出 root。 [GitHub](https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/deepagents/backends/filesystem.py)

权限中间件也要谨慎看。 `PermissionMiddleware` 可以对 filesystem read/write 做规则控制，但源码明确显示它不覆盖 execution backend；如果 backend 支持执行而 permissions 没有正确 scoped，还会直接 raise `NotImplementedError` 。 [GitHub+1](https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/deepagents/middleware/permissions.py)

DeepAgents 自己的 threat model 也说得很直白：

```markdown
默认 StateBackend 是 ephemeral；
FilesystemBackend 默认不是强沙盒；
LocalShellBackend 是 opt-in，但 shell 风险高；
用户需要自己用 container / VM 做隔离。
```

同时它把 poisoned memory / skills、prompt injection、arbitrary shell command、OpenAI retention defaults、remote response injection 都列成威胁类别。 [GitHub+1](https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/THREAT_MODEL.md)

所以 Labebe 里用 DeepAgents 的红线是：

```markdown
不要给它真实 Shopify / Amazon / Meta / TikTok token
不要让它自由 shell 到你的主项目
不要让它 unrestricted crawl
不要让它读 ~/.ssh、~/.aws、~/Documents
不要把生图 / CAD / 发布动作交给它直接执行
```

正确做法：

```markdown
默认用 StateBackend 或受控 StoreBackend
文件输出只写 workspace/outputs
外部工具走 HTTP service
shell 只在 Docker sandbox 里开
所有 publish / CAD / safety / commercial claims 必须人审
```

---

## 2\. LangGraph 本身更适合做 Labebe 的“确定性流程主干”

LangGraph 的定位是 long-running, stateful agents。官方 repo 写得很明确：它提供 durable execution、human-in-the-loop、memory、observability、production deployment 等能力。 [GitHub](https://github.com/langchain-ai/langgraph)

源码里的 `StateGraph` 模型也非常适合这个项目：每个 node 读写共享 state，每个 state key 可以有 reducer，graph compile 之后执行。 [GitHub](https://raw.githubusercontent.com/langchain-ai/langgraph/main/libs/langgraph/langgraph/graph/state.py)

这正好适合 Labebe：

```markdown
State:
- truth_base
- product_data
- review_signals
- competitor_signals
- opportunity_radar
- selected_concept
- design_scorecard
- dfm_preflight
- asset_matrix
- approval_status
- demo_outputs
```

LangGraph 还有一个关键能力： `interrupt` 。官方文档说明，interrupt 可以暂停 graph execution、保存当前状态，并在后续 resume；需要 checkpointer 和 thread\_id。 [LangChain Docs](https://docs.langchain.com/oss/python/langgraph/interrupts?utm_source=chatgpt.com)

这对 Labebe 特别关键，因为你必须暂停给人审：

```markdown
CEO strategy approval
Product opportunity approval
Design concept approval
DFM / Safety review
Asset publishing approval
```

Paperclip 的 approval 适合展示；LangGraph 的 interrupt 适合真实执行。

---

## 3\. DeepAgents + LangGraph 用在 Labebe 时，我建议这样设计

## 3.1 不要做“全自由 Agent Team”，要做“状态机 + 专家 Agent”

错误做法：

```markdown
给一个 CEO Agent 一个大目标：
“请你从评论到竞品到新品到生图到 CAD 到视频全部完成。”
```

这会失控，且很难演示稳定。

正确做法：

```markdown
LangGraph 负责阶段顺序；
DeepAgents 负责每个阶段里的复杂推理；
Paperclip 负责把过程展示成 AI 团队。
```

推荐主流程：

```markdown
START
  ↓
load_truth_base
  ↓
ingest_labebe_product_data
  ↓
voc_analysis_deepagent
  ↓
competitor_radar_deepagent
  ↓
opportunity_synthesis
  ↓
HUMAN_APPROVAL_1: opportunity approval
  ↓
design_brief_deepagent
  ↓
sketch_to_concept_prompt_pack
  ↓
image_generation_service
  ↓
design_director_score_deepagent
  ↓
dfm_safety_preflight_deepagent
  ↓
HUMAN_APPROVAL_2: design / DFM review
  ↓
concept_to_market_asset_matrix
  ↓
demo_video_storyboard
  ↓
END
```

## 3.2 每个节点都要产出文件，而不是只返回聊天文本

```markdown
outputs/
  01_truth_audit.md
  02_voc_clusters.json
  03_competitor_matrix.md
  04_opportunity_radar.json
  05_spacesmart_learning_tower_brief.md
  06_concept_prompt_pack.md
  07_design_director_scorecard.md
  08_dfm_safety_preflight.md
  09_asset_matrix.md
  10_boss_demo_script.md
```

这样前端、Paperclip、短视频都可以复用同一批产物。

---

## 4\. 和 Paperclip 的关系：Paperclip 不是被替代，而是升级成“控制平面”

我之前给 Paperclip 的判断仍然成立：它适合做 Labebe AI Design Studio 的控制台，而不是执行器。

Paperclip 强在：

```markdown
Company
Agents
Issues
Heartbeats
Approvals
Budgets
Activity Log
Board operator view
```

LangGraph / DeepAgents 强在：

```markdown
真实状态机
长任务执行
中断恢复
复杂工具调用
文件产物
可嵌入后端服务
```

所以推荐架构是：

```markdown
Paperclip
  ├── 展示 AI 团队组织结构
  ├── 展示任务树
  ├── 展示审批
  ├── 展示预算和日志
  └── 触发 / 记录 LangGraph run

LangGraph Runtime
  ├── 运行真实 Labebe Design Studio workflow
  ├── 调 DeepAgents 专家
  ├── 写 outputs
  ├── 处理 human interrupt
  └── 供前端读取 run state

DeepAgents
  ├── VOC analyst
  ├── competitor analyst
  ├── design strategist
  ├── design director
  ├── DFM / safety preflight
  └── concept-to-market producer
```

最终老板看到的是 Paperclip；真实跑活的是 LangGraph；复杂脑力是 DeepAgents。

---

## 5\. 其他项目对比：我的真实推荐排序

## 5.1 总排名

| 排名 | 项目 | 我对 Labebe 的判断 |
| --- | --- | --- |
| 1 | **LangGraph + DeepAgents** | 最适合做真实执行层和可恢复工作流。 |
| 2 | **Paperclip + LangGraph + DeepAgents** | 最适合做世界级老板 Demo。 |
| 3 | **OpenAI Agents SDK** | 适合做轻量、清晰、guardrail 明确的小型 agent 服务。 |
| 4 | **Mastra** | 如果前端 / 后端都想走 TypeScript，非常值得考虑。 |
| 5 | **CrewAI** | 适合快速做“Agent Team 头脑风暴”演示，但不建议做严肃主干。 |
| 6 | **Pydantic AI** | 适合做强类型 Python 子 Agent / 输出校验，不适合单独扛整个 AI 公司 Demo。 |
| 7 | **Microsoft Agent Framework** | 很值得关注，但对你当前项目偏重，且更适合 Microsoft / Azure /.NET/Python 企业栈。 |
| 8 | **AutoGen / AG2** | 可做研究式多 Agent 对话，但我不建议作为 Labebe 新项目主干。原 AutoGen 已维护模式，AG2 可关注但不是首选。 |

---

## 6\. DeepAgents vs Paperclip vs CrewAI vs OpenAI Agents SDK vs Mastra

## 6.1 关键对比表

| 维度 | Paperclip | LangGraph | DeepAgents | CrewAI | OpenAI Agents SDK | Mastra |
| --- | --- | --- | --- | --- | --- | --- |
| 本质 | AI 公司控制台 | 状态图 / 工作流引擎 | 长任务 Agent harness | Role-based crews + flows | 轻量多 Agent SDK | TS AI 应用框架 |
| 最强点 | 组织、任务、审批、预算、日志 | 状态、恢复、中断、人审 | planning、文件、subagent、长上下文 | 快速搭角色 Agent | handoff、guardrail、tracing | 前后端一体、TS、workflow |
| 是否适合老板 Demo | 很适合 | 需要自己做 UI | 需要自己做 UI | 适合演示但偏“戏剧化” | 需要自己做 UI | 适合做产品前端 |
| 是否适合真实执行 | 中等 | 很强 | 很强 | 中等 | 中等偏强 | 中等偏强 |
| 人审 | 有 approval 概念 | interrupt 很强 | 依赖 HITL middleware / LangGraph | Flow 有 human\_feedback | guardrails / tool approval 思路清晰 | HITL + storage |
| 状态持久化 | Paperclip 自己管 | 强 | 依赖 LangGraph/backend | 有 Flow state | 需要你设计 sessions / storage | storage 支撑 |
| 子 Agent | 持久员工式 | 可编排 | 临时专家式 | 角色式 | handoff/as\_tool | agents/tools/workflows |
| 风险 | 执行器和公网安全 | 工程复杂度 | filesystem/shell 权限 | 容易变角色扮演 | 长流程耐久性要补 | 生态相对新，TS 绑定强 |
| Labebe 推荐用法 | 控制台 | 主流程 | 节点专家 | 快速视频原型 | guardrailed microservice | 前端/TS 产品层 |

---

## 7\. OpenAI Agents SDK：好，但不是这个项目的主干

OpenAI Agents SDK 的源码结构很清楚。 `Agent` 里直接定义 instructions、tools、handoffs、input\_guardrails、output\_guardrails、output\_type、hooks 等； `as_tool` 可以让一个 Agent 被另一个 Agent 当工具调用，handoff 则是把对话交给另一个 Agent。 [GitHub](https://raw.githubusercontent.com/openai/openai-agents-python/main/src/agents/agent.py)

Guardrails 文档也很实用：input guardrails 可以在 agent 执行前阻断，output guardrails 检查最终输出，tool guardrails 包裹 custom function tools；但文档也说明了边界，比如 input guardrails 只跑在第一个 agent，output guardrails 只看 final output，tool guardrails 不覆盖 hosted tools / built-in execution tools / handoff 本身。 [OpenAI GitHub](https://openai.github.io/openai-agents-python/guardrails/)

它适合 Labebe 的地方：

```markdown
1. 做一个 Design Director micro-agent
2. 做一个 claims guardrail
3. 做一个 DATA_TRUTH checker
4. 做一个 structured output generator
5. 做一个轻量 FastAPI service
```

但它不适合单独扛：

```markdown
VOC → 竞品 → 设计 brief → 人审 → 生图 → DFM → 资产矩阵 → 视频脚本
```

这种长流程。原因不是 SDK 不好，而是你还要自己补很多 durable workflow、checkpoint、approval state、UI 和 replay 逻辑。它更像好用的 agent building block，不是完整 AI Design Studio orchestration layer。

---

## 8\. CrewAI：适合“演示 Agent Team 头脑风暴”，但我不建议做核心执行层

CrewAI 的 repo 说明很清楚：它有两类抽象，Crews 用于 role-based autonomy / collaborative intelligence，Flows 用于 event-driven workflows、state management、production control。 [GitHub](https://github.com/crewaiinc/crewai)

这对你说的“AI Team 头脑风暴”非常适合。比如：

```markdown
VOC Agent:
  “评论里小空间痛点强。”

Competitor Agent:
  “竞品 foldable learning tower 视觉表达弱。”

Design Director:
  “Labebe 应该走 warm oak + cream，避免塑料感。”

DFM Agent:
  “hinge 处可能有夹手风险。”

GTM Agent:
  “这个功能适合 TikTok 对比视频。”
```

CrewAI 的 Human Feedback in Flows 有 `@human_feedback` 装饰器，能暂停 Flow 给人审；task 也有 `human_input` flag，可以在最终答案前请求人工输入。 [CrewAI Documentation+1](https://docs.crewai.com/en/learn/human-feedback-in-flows?utm_source=chatgpt.com)

但是，我不建议把它作为 Labebe 核心执行层，原因是：

```markdown
1. role-play 很快，但严格状态机和产物治理不如 LangGraph 清晰；
2. 对“哪些节点必须中断、哪些输出必须写入 truth base”这种强约束，需要额外工程；
3. 对老板演示可以很热闹，但对董事会安全度未必最好；
4. 你真正需要的是证据链、审批链、产物链，不是 Agent 互相聊天。
```

我会把 CrewAI 放在：

```markdown
快速生成 90 秒短视频里的 Agent War Room 原型
或内部概念验证
```

不放在正式 Demo 主干。

---

## 9\. Mastra：如果你想把前端和 Agent Runtime 都做成 TypeScript，它很值得看

Mastra 是 TypeScript-first 的 AI application / agent framework，repo 里明确说它支持 React、Next.js、Node 或 standalone server；包含 model routing、agents、workflows、MCP、memory、RAG、evals、observability。 [GitHub](https://github.com/mastra-ai/mastra)

它的 workflow 设计也值得注意：README 里说 workflows 用 `.then()` 、`.branch()` 、`.parallel()` 组织复杂多步流程；HITL 可以 suspend agent/workflow，并借助 storage indefinitely pause/resume。 [GitHub](https://github.com/mastra-ai/mastra)

Mastra 还有 Inngest workflow engine 适配，代码示例用 `createStep` 、 `createWorkflow` 、`.then()` 、`.dountil()` 等来编排，并说明 Inngest runtime 可水平扩展、支持 watching / eventing。 [GitHub](https://github.com/mastra-ai/mastra/tree/main/workflows)

它适合 Labebe 的地方：

```markdown
如果你的前端 Demo 是 Next.js / React，
并且你想把 AI Growth Studio、API、workflow、agent endpoints 做成一个 TS monorepo，
Mastra 很合适。
```

但我的判断是：

```markdown
如果你重点是数据分析、脚本、CSV、Python 图像/CAD pipeline、LangChain生态、LangSmith调试，
LangGraph + DeepAgents 更适合第一版。
```

Mastra 可以作为：

```markdown
前端产品化层
AI Studio API 层
Next.js app 内嵌 agent workflow
```

但不作为第一选择的核心设计研究 runtime。

---

## 10\. Pydantic AI：适合做“强类型子 Agent”，不适合做 Labebe 主舞台

Pydantic AI 的定位是 Python agent framework，强调 Pydantic-style 类型验证和生产级应用开发。官方 API 文档说明，agent run 会构建 internal agent graph，并且可迭代 agent graph 节点、流式消费模型和工具事件。 [GitHub+1](https://github.com/pydantic/pydantic-ai?utm_source=chatgpt.com)

它和 DBOS 的 durable execution 组合也值得注意：Pydantic 官方文章说 DBOS 会把 agent.run 包装成 durable workflow，model calls / MCP / tool invocations 可 checkpoint，crash 后从数据库恢复，不重复消耗 token；还可以和 Logfire 做 observability。 [Pydantic](https://pydantic.dev/articles/pydantic-ai-dbos?utm_source=chatgpt.com)

我会把它用于：

```markdown
1. 严格 JSON schema 输出
2. DATA_TRUTH checker
3. concept_scorecard validator
4. claims_guardrail
5. bom_assumption structured generator
```

不把它作为主流程，因为 LangGraph 在多节点流程、人审中断、状态图方面更直接。

---

## 11\. Microsoft Agent Framework：技术上强，但现在不是 Labebe 第一选择

Microsoft Agent Framework repo 显示它支持 Python 和.NET，重点包括 graph-based workflows、streaming、checkpointing、human-in-the-loop、time-travel、DevUI、OpenTelemetry observability、多 provider、middleware 等。 [GitHub](https://github.com/microsoft/agent-framework)

如果你的公司技术栈是：

```markdown
Azure
Microsoft Foundry
.NET
Enterprise governance
Durable Task
OpenTelemetry
```

它很值得深入。但对 Labebe 当前 Demo 来说，它有两个问题：

```markdown
1. 生态和样例会更偏 Microsoft / Azure；
2. 你现在更需要快速做出视觉冲击 + AI Design Studio 工作流，而不是企业云平台迁移。
```

我的建议：

```markdown
关注，但不作为第一版 Demo 主栈。
```

---

## 12\. AutoGen / AG2：不要用原 AutoGen 做新项目主干

原 Microsoft AutoGen repo 现在明确写着已经进入 maintenance mode，不再加新 features/enhancements，由社区维护。 [GitHub](https://github.com/microsoft/autogen?utm_source=chatgpt.com)

AG2 是 AutoGen 后续社区方向，支持多 Agent 协作、工具、HITL 等，官方资料也显示它有 human-in-the-loop hooks 和 subagents 等能力。 [GitHub+1](https://github.com/ag2ai/ag2?utm_source=chatgpt.com)

但我不建议你把 Labebe 新项目押在 AG2 上。原因：

```markdown
1. Labebe 不是研究式 multi-agent chat；
2. 你更需要确定性流程、审批、产物、数据真实性；
3. LangGraph + DeepAgents 已经更贴合“长任务 + 状态机 + 人审”；
4. Paperclip 已经能提供更好的 AI Team 展示感。
```

AG2 可以参考 multi-agent conversation 设计，但不是主栈。

---

## 13\. 对 Labebe 各个 Demo 的最佳技术选型

## 13.1 Design Opportunity Radar

目标：

```markdown
评论、销量、竞品、趋势 → 机会雷达
```

推荐：

```markdown
LangGraph 主流程
DeepAgents: VOC Analyst / Competitor Radar / Strategy Synthesizer
Paperclip: 记录任务和审批
```

不推荐 CrewAI 单独做，因为它容易生成“很像讨论”的文本，但不一定有可复用 state 和证据链。

---

## 13.2 Agent Team 头脑风暴短视频

目标：

```markdown
让老板看到 AI 团队如何讨论新品方向
```

推荐：

```markdown
Paperclip + 前端 War Room + 预生成 DeepAgents 输出
```

可选：

```markdown
CrewAI 快速生成对话脚本
```

但最终展示应该用 Paperclip / 自定义前端，而不是直接播放 CrewAI console logs。

---

## 13.3 草图 → 概念图 → 迭代

目标：

```markdown
设计师草图变成多风格产品方向
```

推荐：

```markdown
LangGraph:
  sketch_intake
  design_route_generation
  prompt_pack_generation
  image_generation_service
  design_director_score
  dfm_preflight
  human_review
```

DeepAgents 负责：

```markdown
生成 prompt pack
解释设计路线
写下一轮迭代建议
```

外部服务负责：

```markdown
生图 / 渲染 / 图像编辑
```

---

## 13.4 Custom Toy Kitchen Builder

目标：

```markdown
家长输入孩子年龄、房间、风格、功能 → AI 定制玩具厨房方案
```

推荐：

```markdown
Frontend:
  Next.js / React

Workflow:
  LangGraph

Agent:
  DeepAgent Design Strategist
  DeepAgent Design Director
  DFM Preflight

Data:
  module_schema.json
  product_seed.json
  DATA_TRUTH.md

Output:
  concept brief
  render prompt
  module diagram
  recommended Labebe bundle
  waitlist landing block
```

如果你想纯 TS 产品化，Mastra 也适合这一条。

---

## 13.5 竞品大数据 → 产品设计方案

目标：

```markdown
竞品 listing / 图片 / 差评 / 价格带 → 产品白区
```

推荐：

```markdown
LangGraph + DeepAgents + 受控数据输入
```

不推荐第一版做 unrestricted crawler。用：

```markdown
手动导出的 CSV
公开样本页面截图
人工整理竞品样本
第三方工具导出
```

因为 DeepAgents 自身也警告 remote response / context injection / filesystem-shell 风险，外部抓取内容必须进入隔离处理。 [GitHub+1](https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/THREAT_MODEL.md)

---

## 13.6 Design Director Agent

目标：

```markdown
AI 概念图审美评分、品牌匹配、下一轮 prompt
```

推荐：

```markdown
DeepAgents + DESIGN.md + structured output
```

输出：

```markdown
{
  "brand_fit": 86,
  "parent_taste": 82,
  "montessori_calmness": 88,
  "giftability": 70,
  "manufacturing_realism": 61,
  "problems": [],
  "next_prompt": ""
}
```

可以用 OpenAI Agents SDK 或 Pydantic AI 来加强 schema / guardrail。

---

## 13.7 DFM / Safety Preflight

目标：

```markdown
概念图 / 设计 brief → 结构、安全、包装、成本初审
```

推荐：

```markdown
LangGraph deterministic checklist
+ DeepAgent DFM reviewer
+ Human approval interrupt
```

不要让 LLM 直接宣布：

```markdown
safe
certified
factory-ready
production CAD
```

只说：

```markdown
preflight
risk flags
engineering review required
```

---

## 14\. 我推荐的最终项目结构

```markdown
labebe-ai-design-studio/
│
├── apps/
│   ├── web/
│   │   ├── Labebe Consumer Demo
│   │   ├── AI Design Studio Frontend
│   │   ├── Opportunity Radar
│   │   ├── Agent War Room
│   │   ├── Sketch-to-Concept
│   │   ├── Custom Toy Kitchen Builder
│   │   └── Asset Matrix
│   │
│   └── paperclip-sync/
│       ├── sync LangGraph run -> Paperclip issue comments
│       └── sync approvals / outputs
│
├── runtime/
│   ├── langgraph_app/
│   │   ├── graphs/
│   │   │   └── labebe_design_studio_graph.py
│   │   ├── nodes/
│   │   │   ├── truth_audit.py
│   │   │   ├── voc_analysis.py
│   │   │   ├── competitor_radar.py
│   │   │   ├── opportunity_synthesis.py
│   │   │   ├── design_brief.py
│   │   │   ├── design_director.py
│   │   │   ├── dfm_preflight.py
│   │   │   └── asset_matrix.py
│   │   ├── agents/
│   │   │   ├── voc_deepagent.py
│   │   │   ├── competitor_deepagent.py
│   │   │   ├── design_director_deepagent.py
│   │   │   └── dfm_deepagent.py
│   │   └── api.py
│   │
│   └── services/
│       ├── image_generation_service/
│       ├── cad_direction_service/
│       ├── video_storyboard_service/
│       └── competitor_sample_service/
│
├── workspace/
│   ├── docs/
│   │   ├── DESIGN.md
│   │   ├── DATA_TRUTH.md
│   │   ├── FORBIDDEN_CLAIMS.md
│   │   ├── AGENTS.md
│   │   └── REFERENCE_MAP.md
│   │
│   ├── data/
│   │   ├── truth_base_frozen.csv
│   │   ├── products_seed.json
│   │   ├── review_signal_samples.csv
│   │   ├── competitor_samples.csv
│   │   └── trend_samples.csv
│   │
│   ├── outputs/
│   │   ├── opportunity_radar.md
│   │   ├── spacesmart_learning_tower_brief.md
│   │   ├── design_scorecard.md
│   │   ├── dfm_safety_preflight.md
│   │   ├── concept_to_market_asset_matrix.md
│   │   └── boss_demo_script.md
│   │
│   └── assets/
│       ├── concept_images/
│       ├── video_posters/
│       └── demo_screenshots/
```

---

## 15\. LangGraph + DeepAgents 的核心代码骨架

下面是我建议的方向，不是最终完整代码，但结构应该这样。

```markdown
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

class LabebeDesignState(TypedDict, total=False):
    run_id: str
    truth_base_path: str
    product_data_path: str
    selected_product: str

    voc_clusters_path: str
    competitor_matrix_path: str
    opportunity_radar_path: str

    selected_opportunity: str
    opportunity_approved: bool

    design_brief_path: str
    concept_prompt_pack_path: str
    concept_images: list[str]

    design_scorecard_path: str
    dfm_preflight_path: str
    design_approved: bool

    asset_matrix_path: str
    boss_demo_script_path: str

def load_truth_base(state: LabebeDesignState):
    return {
        "truth_base_path": "workspace/data/truth_base_frozen.csv",
        "product_data_path": "workspace/data/products_seed.json",
    }

def voc_analysis(state: LabebeDesignState):
    # call DeepAgent VOC specialist
    result_path = run_voc_deepagent(state)
    return {"voc_clusters_path": result_path}

def competitor_radar(state: LabebeDesignState):
    result_path = run_competitor_deepagent(state)
    return {"competitor_matrix_path": result_path}

def opportunity_synthesis(state: LabebeDesignState):
    result_path = synthesize_opportunity_radar(state)
    return {"opportunity_radar_path": result_path}

def approve_opportunity(state: LabebeDesignState):
    decision = interrupt({
        "type": "opportunity_approval",
        "summary": state["opportunity_radar_path"],
        "question": "Approve one opportunity for concept design?"
    })
    return {
        "selected_opportunity": decision["selected_opportunity"],
        "opportunity_approved": decision["approved"],
    }

def design_brief(state: LabebeDesignState):
    path = run_design_brief_deepagent(state)
    return {"design_brief_path": path}

def design_director_score(state: LabebeDesignState):
    path = run_design_director_deepagent(state)
    return {"design_scorecard_path": path}

def dfm_preflight(state: LabebeDesignState):
    path = run_dfm_deepagent(state)
    return {"dfm_preflight_path": path}

def approve_design(state: LabebeDesignState):
    decision = interrupt({
        "type": "design_and_dfm_approval",
        "design_scorecard": state["design_scorecard_path"],
        "dfm_preflight": state["dfm_preflight_path"],
        "question": "Approve concept for launch-test asset generation?"
    })
    return {"design_approved": decision["approved"]}

def asset_matrix(state: LabebeDesignState):
    path = run_asset_matrix_deepagent(state)
    return {"asset_matrix_path": path}

builder = StateGraph(LabebeDesignState)

builder.add_node("load_truth_base", load_truth_base)
builder.add_node("voc_analysis", voc_analysis)
builder.add_node("competitor_radar", competitor_radar)
builder.add_node("opportunity_synthesis", opportunity_synthesis)
builder.add_node("approve_opportunity", approve_opportunity)
builder.add_node("design_brief", design_brief)
builder.add_node("design_director_score", design_director_score)
builder.add_node("dfm_preflight", dfm_preflight)
builder.add_node("approve_design", approve_design)
builder.add_node("asset_matrix", asset_matrix)

builder.add_edge(START, "load_truth_base")
builder.add_edge("load_truth_base", "voc_analysis")
builder.add_edge("voc_analysis", "competitor_radar")
builder.add_edge("competitor_radar", "opportunity_synthesis")
builder.add_edge("opportunity_synthesis", "approve_opportunity")
builder.add_edge("approve_opportunity", "design_brief")
builder.add_edge("design_brief", "design_director_score")
builder.add_edge("design_director_score", "dfm_preflight")
builder.add_edge("dfm_preflight", "approve_design")
builder.add_edge("approve_design", "asset_matrix")
builder.add_edge("asset_matrix", END)

graph = builder.compile(checkpointer=MemorySaver())
```

第一版可以用 `MemorySaver` ，正式一点再换 SQLite / Postgres checkpointer。

---

## 16\. DeepAgent 专家示例：Design Director

```markdown
from deepagents import create_deep_agent
from deepagents.backends import StateBackend

design_director_agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-5",
    backend=StateBackend(),
    system_prompt="""
You are the Labebe Design Director Agent.

Read DESIGN.md and DATA_TRUTH.md before making claims.

Score product concepts on:
- brand_fit
- parent_taste
- montessori_calmness
- giftability
- child_appeal
- home_aesthetic
- manufacturing_realism

Never invent:
- product price
- review count
- certifications
- safety approval
- production CAD readiness

Output:
1. Scorecard
2. What works
3. What feels off-brand
4. Specific revision instructions
5. Next prompt
6. Human review notes
""",
    tools=[],
    interrupt_on={
        "write_file": True,
        "edit_file": True,
        "execute": True,
    }
)
```

注意： `execute` 只是 interrupt，不等于安全沙盒。真正要执行脚本，必须放到 Docker / Modal / Daytona / AgentCore / 自建 sandbox service 里。DeepAgents repo 也把 sandbox integrations 放在 partners 目录，包括 AgentCore、Daytona、Modal、QuickJS、Runloop 等。 [GitHub](https://github.com/langchain-ai/deepagents/tree/main/libs)

---

## 17\. 我对 DeepAgents 的红队意见

## P0 风险 1：它的“信任 LLM”模型不能直接接真实业务动作

DeepAgents README 自己说 security model 是 “trust the LLM”，agent 能做任何 tool 允许的事，安全边界必须在 tool / sandbox 层 enforce。 [GitHub](https://github.com/langchain-ai/deepagents)

所以：

```markdown
不能让 DeepAgent 直接发邮件
不能让 DeepAgent 直接改 Shopify
不能让 DeepAgent 直接发广告
不能让 DeepAgent 直接访问真实 Amazon Seller
不能让 DeepAgent 直接生成 production CAD claim
```

## P0 风险 2：Skills / Memory 也可能被污染

DeepAgents threat model 把 poisoned memory / skills 列为高风险。 [GitHub](https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/THREAT_MODEL.md)

Labebe 必须：

```markdown
skills/ 只读、人工审核
DATA_TRUTH.md 只读
DESIGN.md 只读
外部网页内容先变成 sample，再喂给 agent
```

## P0 风险 3：Shell 执行不能放在主机

如果要跑：

```markdown
python scripts/voc_cluster.py
python scripts/render_asset_matrix.py
node scripts/export_video_storyboard.js
```

必须放在：

```markdown
Docker sandbox
临时 workspace
无真实 secrets
无主目录挂载
只读 data/
只写 outputs/
```

---

## 18\. 7 天落地方案：Paperclip + LangGraph + DeepAgents

## Day 1：数据真实性和 workflow skeleton

交付：

```markdown
workspace/docs/DATA_TRUTH.md
workspace/docs/DESIGN.md
workspace/data/products_seed.json
workspace/data/truth_base_frozen.csv
runtime/langgraph_app/graphs/labebe_design_studio_graph.py
```

先写死真实 Labebe seed：

```markdown
46 products
furniture 17
rockers-ride-ons 13
pretend-play 9
activity-educational-toys 6
new-in 1
Pink Unicorn Plush Rocker $109.99 / 18 reviews
Cream Wooden Play Kitchen $129.99 / 9 reviews
Natural Wood Montessori Shelf $114.99 / 9 reviews
```

## Day 2：VOC + Competitor Radar

交付：

```markdown
VOC clusters
Competitor matrix
Opportunity radar
```

先用 demo sample，但标注：

```markdown
Demo Sample，需要真实 review export 验证。
```

## Day 3：SpaceSmart Learning Tower 主线

交付：

```markdown
spacesmart_learning_tower_brief.md
design_requirements.json
concept_prompt_pack.md
```

## Day 4：Design Director + DFM

交付：

```markdown
design_scorecard.md
dfm_safety_preflight.md
human_review_packet.md
```

## Day 5：Custom Toy Kitchen Builder

交付：

```markdown
toy_kitchen_module_schema.json
mini_bakery_kitchen_corner.md
custom_builder_frontend_mock
render_prompt_pack.md
```

## Day 6：Concept-to-Market Asset Matrix

交付：

```markdown
PDP block
Amazon A+ outline
TikTok scripts
Meta carousel
Google image brief
Email waitlist block
```

## Day 7：Paperclip + 前端 + 短视频

交付：

```markdown
Paperclip AI team dashboard
LangGraph run timeline
AI Design Studio frontend
90 秒视频
15 分钟老板讲稿
QA checklist
```

---

## 19\. 最终演示结构

## 画面 1：Paperclip

```markdown
Labebe AI Design Studio
Agents:
- Product Innovation Director
- VOC Intelligence Analyst
- Competitive Radar Analyst
- Design Director
- DFM & Safety Preflight
- Concept-to-Market Agent

Issues:
- Opportunity Radar
- VOC to Product Concept
- Sketch-to-Concept
- Custom Toy Kitchen Builder
- DFM Preflight
- Asset Matrix
```

## 画面 2：LangGraph Run Timeline

```markdown
truth_base_loaded
voc_analysis_done
competitor_radar_done
opportunity_approval_pending
design_brief_done
dfm_preflight_done
asset_matrix_done
```

## 画面 3：AI Design Studio Frontend

```markdown
Opportunity Radar
Agent War Room
Sketch-to-Concept
Custom Toy Kitchen Builder
Design Director Scorecard
DFM Preflight
Concept-to-Market Matrix
```

## 画面 4：短视频成片

```markdown
From customer signals to product design.
Design smarter. Prototype faster. Test earlier.
```

---

## 20\. 我的最终选择建议

## 最推荐组合

```markdown
Paperclip
+ LangGraph
+ DeepAgents
+ 自定义 Labebe AI Design Studio 前端
```

## 为什么不是只用 Paperclip？

因为 Paperclip 更像控制台，不是最好的真实 workflow runtime。复杂数据链路、人审中断、状态恢复、文件产物、图像/CAD服务编排，用 LangGraph 更稳。

## 为什么不是只用 DeepAgents？

因为 DeepAgents subagents 是临时专家，不是持久组织；它没有天然的老板控制台、预算、审批、任务树和 AI company 展示感。

## 为什么不是只用 CrewAI？

因为 CrewAI 很适合“Agent 角色讨论”，但 Labebe 需要的是：

```markdown
数据真实性
确定状态机
人审中断
产物文件
可复盘证据链
```

LangGraph 更贴合。

## 为什么不是只用 OpenAI Agents SDK？

它很适合做小而清晰的 agent 服务、handoff、guardrail、tracing，但 Labebe 的主流程是长链路、多节点、多审批、多产物，需要更强工作流引擎。

## 为什么不是只用 Mastra？

如果你决定全项目都走 TypeScript / Next.js / Node，Mastra 是强候选。但当前 Labebe 的数据分析、文件处理、Python 脚本、LangChain/DeepAgents生态更适合用 LangGraph 主导。

---

## 21\. 最终一句话方案

```markdown
用 Paperclip 做 Labebe AI Design Studio 的董事会级控制台；
用 LangGraph 做真实可恢复、可中断、可审批的产品创新流程；
用 DeepAgents 做 VOC、竞品、设计、DFM、GTM 等复杂专家任务；
用独立前端做世界级视觉演示；
用 DATA_TRUTH.md 和 DESIGN.md 控制真实性与审美；
用 Human Approval 阻断所有产品、安全、CAD、发布和商业数字风险。
```

这会比单独用 Paperclip、单独用 CrewAI、单独用 DeepAgents都更强。

老板最后看到的不是：

```markdown
我们又试了一个 Agent 框架。
```

而是：

```markdown
Labebe 已经有了一个 AI 产品创新操作系统：
它能从评论和竞品里找设计机会，
从草图和数据里生成产品概念，
用 Design Director 控审美，
用 DFM / Safety 做工程初审，
用 Concept-to-Market 生成上市测试素材，
并且整个过程有任务、有审批、有日志、有证据、有复盘。
```

我会把直接挂 Claude Code/Kimi/Codex 的 CLI runtime，与 LangGraph/DeepAgents 的可编排执行层对比，重点看状态、审批、恢复、安全和 Labebe Demo 分工。

我先确认一个关键实现差异：Claude/Codex 是 Paperclip 内置 adapter，Kimi 更可能要走 process、HTTP 或自定义桥接。直接 CLI 路线快但会影响 session、日志、成本统计和失败恢复。

## 结论：区别非常大，但不是“能不能做”，而是“谁掌握流程控制权”

你说的方案：

```markdown
Paperclip
  ├── Claude Code runtime
  ├── Kimi Code runtime
  └── Codex runtime
```

**完全可以做，而且是最快能出效果的路线。**

但它和我前面说的：

```markdown
Paperclip + LangGraph + DeepAgents
```

核心区别不是模型能力，而是：

> **直接给 Paperclip 配 ClaudeCode / KimiCode / Codex，本质是“AI 员工自己推进任务”；  
> Paperclip + LangGraph/DeepAgents，本质是“确定性流程驱动 AI 专家完成每一步”。**

换句话说：

```markdown
Paperclip + ClaudeCode/KimiCode/Codex
= AI 公司作战室，强展示、强灵活、快启动，但流程稳定性靠 prompt 和 agent 自律。

Paperclip + LangGraph/DeepAgents
= AI 产品创新流水线，强状态、强审批、强可恢复、强产物结构，但工程量更大。
```

我现在对 Labebe 的最终建议是：

> **第一阶段直接用 Paperclip 挂 ClaudeCode / Codex / KimiCode 做世界级 Demo；  
> 第二阶段把关键流程固化成 LangGraph；  
> 第三阶段让 Paperclip 只做控制台和审批台，LangGraph 做真实执行层。**

Labebe 当前要展示的不是普通网页，而是“网站升级 + AI 营销素材生产 + AI 辅助产品设计 + 可审批增长工作流”。你之前的方案里已经明确，Labebe 不应只是商品网格站，而要升级成“场景化儿童成长空间品牌站 + 多渠道素材中台 + AI 内容生产工作流”。  
同时，你已有审计结论也一直提醒：不能把假设数字、ROI、评论、销量、认证、效果承诺混成硬事实，必须做 `truth_base_frozen.csv` 、 `DATA_TRUTH.md` 、Fact / Estimate / Hypothesis 分层。[Response: AI技术深度调研](https://chatgpt.com/g/g-p-69463ae4056481919050c99739eed58c/c/69e9e6d6-c278-83aa-81a8-532da6f2a1ba?messageId=b2fc96e9-a3e4-494d-a0a3-81d6b374ec5a&conversation_save=1)

所以这次的判断要非常务实：

```markdown
直接配 ClaudeCode / KimiCode / Codex：适合快速做出“AI 设计团队作战室”。
LangGraph/DeepAgents：适合把作战室背后的关键流程做成可重复、可恢复、可验收的生产系统。
```

---

## 1\. 直接 Paperclip + ClaudeCode / KimiCode / Codex 到底是什么架构？

Paperclip 自己的产品定义说得很清楚：它是 autonomous AI companies 的 control plane；每个 agent 的身份由 adapter type + config 决定，Claude Code 可以用 `CLAUDE.md` ，OpenClaw 可以用自己的文件，裸脚本可以用 CLI args，Paperclip 不规定 runtime 格式。更关键的一句是： **Paperclip 是 control plane，不是 execution plane** 。 [GitHub](https://github.com/paperclipai/paperclip/blob/master/doc/PRODUCT.md)

所以直接配 runtime 的真实结构是：

```markdown
Paperclip
  管公司、组织图、Issue、Heartbeat、预算、审批、日志

ClaudeCode / Codex / KimiCode
  真正读文件、写文件、跑命令、做分析、生成代码、生成文档

Paperclip Heartbeat
  每次唤醒一个 runtime，让它继续处理当前 Issue
```

Paperclip README 也把它的系统边界列得很清楚：Org Chart & Agents、Work & Task System、Heartbeat Execution、Workspaces & Runtime；agent 可以是 Claude Code、Codex、CLI agents、HTTP/webhook bots 等，只要能接收 heartbeat，就能被“雇佣”。 [GitHub](https://github.com/paperclipai/paperclip)

这意味着，你直接把 ClaudeCode / KimiCode / Codex 配到 Paperclip，得到的是：

```markdown
AI 公司操作系统
+ 三类强执行员工
```

不是：

```markdown
强类型产品创新流水线
```

---

## 2\. 直接配 runtime 的优势：为什么我认为它应该作为第一阶段

## 2.1 启动最快，最适合做“老板看得懂”的作战室

Paperclip 自带公司、Agent、Issue、Heartbeat、Budget、Approval、Activity Log。你把 ClaudeCode / Codex / KimiCode 接进去后，老板可以马上看到：

```markdown
Product Innovation Director 正在拆任务
VOC Analyst 正在分析评论
Competitive Radar Analyst 正在看竞品
Design Director 正在打分
DFM Agent 正在标风险
GTM Agent 正在生成素材矩阵
```

这比 LangGraph 的 node graph 更像一个“公司在运转”。  
LangGraph 更像工程流，Paperclip 更像管理驾驶舱。

对 Labebe 的世界级 Demo 来说，Paperclip 直接挂 runtime 的视觉表达非常强：

```markdown
Org Chart
Issue Tree
Heartbeat Log
Approval Queue
Budget Usage
Activity Log
```

这些是 LangGraph 默认不给你的。

---

## 2.2 ClaudeCode / Codex 是 Paperclip 的一等适配对象

Paperclip 的 process adapter 文档明确说，它主要用于在同一台机器上运行 Claude Code 和 Codex 这类 CLI agent；内置 process adapters 包括 `claude_local` 和 `codex_local` 。 [Paperclip AI](https://paperclipai-paperclip.mintlify.app/agents/process-adapter)

Claude adapter 有 `cwd` 、 `instructionsFilePath` 、 `model` 、 `effort` 、 `promptTemplate` 、 `maxTurnsPerRun` 、 `timeoutSec` 等配置；文档还写了 Claude session 会在 agent 有保存的 sessionId 且 cwd 匹配时自动恢复，并会把 Paperclip skills 注入给 Claude。 [Paperclip AI](https://paperclipai-paperclip.mintlify.app/agents/process-adapter)

Codex adapter 也有类似配置，并支持 `modelReasoningEffort` 、 `search` 、skills auto-injection 等；Paperclip 文档说明 Codex adapters 会把 Paperclip skills 注入到 `$CODEX_HOME/skills` ，让 Codex 能发现 `$paperclip` skill。 [Paperclip AI](https://paperclipai-paperclip.mintlify.app/agents/process-adapter)

所以：

```markdown
ClaudeCode + Paperclip
Codex + Paperclip
```

是比较自然的组合。

---

## 2.3 对“写代码、改前端、生成文档、整理报告”非常强

Labebe 这个 Demo 里有大量工作其实不是复杂 workflow，而是：

```markdown
重构前端页面
生成 DESIGN.md
生成 DATA_TRUTH.md
写 SKU 数据
写 PDP
写 AI Growth Studio 页面
做 boss demo script
写短视频分镜
把输出整理成 Markdown / JSON / React components
```

这些任务 ClaudeCode / Codex / KimiCode 非常擅长。

如果你用 Paperclip 直接分配 Issue，例如：

```markdown
Issue: Build Custom Toy Kitchen Builder page
Assignee: Codex Frontend Agent

Issue: Write Design Director scoring prompt and JSON schema
Assignee: Claude Design Director Agent

Issue: Research competitor reference pages and summarize design patterns
Assignee: Kimi Research Agent
```

它们可以很快把文件产物做出来。

对于第一版 Demo，这比先搭 LangGraph 更快。

---

## 3\. 直接配 runtime 的根本短板：流程控制权在 agent，不在系统

这是最重要的区别。

Paperclip 直接挂 ClaudeCode / KimiCode / Codex 时，实际执行逻辑是：

```markdown
Paperclip: 你醒来，看看任务，继续工作
Agent runtime: 好，我自己判断读什么、写什么、调用什么、何时结束
```

这很灵活，但会带来五个问题。

---

## 3.1 状态不是强类型状态，而是 Issue + Comment + 文件 + CLI session

LangGraph 里你可以定义：

```markdown
class LabebeDesignState(TypedDict):
    truth_base_path: str
    voc_clusters: list
    opportunity_radar: dict
    selected_opportunity: str
    approval_status: str
    design_brief_path: str
    dfm_risks: list
    asset_matrix_path: str
```

每一步只能读写指定 state。

而 Paperclip 直接 runtime 的状态更像：

```markdown
Issue description
Issue comments
Agent previous session
workspace files
agent 自己的记忆
```

这种方式适合开放式工作，不适合严格保证：

```markdown
VOC 必须先跑
Data Truth 必须先验证
Opportunity 必须审批
Design Brief 必须是 JSON
DFM 必须输出固定 schema
Asset Matrix 必须等待 approval
```

你可以靠 prompt 约束，但不是系统级硬约束。

---

## 3.2 Human approval 更偏“任务级审批”，不是“流程节点级中断”

Paperclip 有 Approval，很适合老板演示：

```markdown
CEO Strategy Approval
Design Concept Approval
DFM Review Approval
Publish Approval
```

但直接 runtime 模式里，agent 内部做了什么，通常由 CLI runtime 自己管理。Claude Code 有自己的 permission system，Codex 有自己的 sandbox / approval policy，Kimi CLI 也有自己的 approval 机制。Claude Code 默认有细粒度权限：读文件通常不需要批准，bash 和文件修改需要批准；规则支持 allow / ask / deny，且 deny 优先。 [Claude](https://code.claude.com/docs/en/permissions)

问题是：Paperclip 的 heartbeat 是 headless / non-interactive 场景。为了让 agent 能跑完，很多配置会倾向于“自动通过”或“跳过权限”。Paperclip 当前 master 源码里的 Claude adapter 配置说明甚至写到 `dangerouslySkipPermissions` 默认 true，因为 Paperclip 用 headless print mode，无法回答交互式 permission prompt；Codex adapter 源码里也有 `DEFAULT_CODEX_LOCAL_BYPASS_APPROVALS_AND_SANDBOX = true` 。 [GitHub+1](https://raw.githubusercontent.com/paperclipai/paperclip/master/packages/adapters/claude-local/src/index.ts)

这就产生一个关键矛盾：

```markdown
想自动跑：需要减少交互审批。
想安全跑：不能完全放开权限。
```

LangGraph 的区别在于：审批点不是 runtime 临时弹窗，而是 graph 里的显式 `interrupt()` 节点。LangGraph 文档说明，interrupt 可以在任意 node 暂停 graph execution，把状态保存到 persistence layer，然后无限期等待外部输入再恢复。 [LangChain Docs](https://docs.langchain.com/oss/python/langgraph/interrupts)

这就是直接 Paperclip runtime 和 LangGraph 的最大差别之一：

```markdown
Paperclip 直接 runtime：
“Agent 自己工作，关键任务进入 in_review。”

LangGraph：
“流程走到这个节点必须暂停，审批结果作为 state 写回，下一步才能执行。”
```

---

## 3.3 可恢复性不同：CLI session resume 不是 workflow checkpoint

Claude / Codex 可以恢复 session，Paperclip 也会保存 session 信息。Paperclip process adapter 文档写明，Claude session 会在 sessionId 和 cwd 匹配时自动恢复。 [Paperclip AI](https://paperclipai-paperclip.mintlify.app/agents/process-adapter)

但这和 LangGraph checkpoint 不是一回事。

CLI session resume 的问题是：

```markdown
它恢复的是对话上下文；
不是每个业务步骤的已完成状态。
```

如果一个 agent 跑了一半：

```markdown
读了数据
写了一半文件
调用了外部服务
生成了部分图片
又失败了
```

重新 heartbeat 后，它可能：

```markdown
重复做
漏做
改写旧文件
误判上次状态
靠聊天记录猜测该继续哪里
```

LangGraph durable execution 的定位就是解决这个：它会在关键点保存工作流进度，恢复时不需要重复处理已经完成的步骤；文档还强调副作用和非确定操作要放进 task / node，以保证 resume 时不要重复执行。 [LangChain Docs](https://docs.langchain.com/oss/python/langgraph/durable-execution)

所以：

```markdown
Paperclip + CLI runtime 的恢复：
偏“对话恢复”。

LangGraph 的恢复：
偏“流程恢复”。
```

对 Labebe 这种：

```markdown
数据导入 → VOC 聚类 → 机会雷达 → 人审 → 设计 brief → 生图 → 设计评分 → DFM → 人审 → 资产矩阵
```

长链路来说，LangGraph 的恢复模型更可靠。

---

## 3.4 产物结构不同：CLI runtime 容易产出漂亮文本，但不一定产出稳定 JSON

直接给 Paperclip agent 一个 Issue，它可能会写出很好的 Markdown：

```markdown
SpaceSmart Foldable Learning Tower
Brand Fit 86
DFM Risks
TikTok Scripts
```

但下一步前端要读取的时候，你更需要：

```markdown
{
  "concept_id": "spacesmart_learning_tower",
  "scores": {
    "brand_fit": 86,
    "manufacturing_realism": 61
  },
  "risks": [
    {
      "type": "pinch_point",
      "severity": "medium",
      "human_review_required": true
    }
  ]
}
```

直接 runtime 可以靠 prompt 要求 JSON，但稳定性取决于 agent 表现。  
LangGraph 更适合把每个 node 输出变成 schema，失败就 retry / validate / block。

这就是为什么我建议：

```markdown
第一阶段让 Paperclip runtime 生成 Markdown + 演示文件；
第二阶段用 wrapper script 或 LangGraph 强制输出 JSON；
第三阶段让前端 Demo 只读结构化 outputs。
```

---

## 3.5 多 agent 可见性强，但内部 subagent 不可见

Kimi Code CLI 自己支持 agents 和 subagents。文档显示，Kimi 的 agent 定义包括 system prompt、可用 tools、subagents；默认 agent 有 `coder` 、 `explore` 、 `plan` 等内置 subagent，subagent 有隔离上下文，可以并行处理任务并保留自己的 context history。 [Moonshot AI](https://moonshotai.github.io/kimi-cli/en/customization/agents.html)

Claude Code 也支持 subagents；DeepAgents 也有 subagents。

但如果你把 KimiCode 当成 Paperclip 的一个 runtime，Kimi 内部开的 subagent：

```markdown
Kimi root agent
  ├── explore subagent
  ├── plan subagent
  └── coder subagent
```

Paperclip 不会把这些内部 subagent 显示成公司员工。Paperclip 只看到：

```markdown
Kimi Research Agent 跑了一次 heartbeat
stdout/stderr
最终输出
```

所以：

```markdown
Paperclip agent = 外部可见员工
Kimi / Claude / DeepAgents subagent = runtime 内部临时专家
```

这不是坏事，但你不能把二者混为一谈。

老板想看的“AI Team 头脑风暴”，应该尽量放在 Paperclip 层：

```markdown
VOC Agent
Competitive Radar Agent
Design Director Agent
DFM Agent
GTM Agent
```

而 runtime 内部 subagent 适合做隐藏执行：

```markdown
Kimi explore subagent 搜参考
Codex coder subagent 改代码
Claude research subagent 总结设计趋势
```

---

## 4\. KimiCode 和 Claude/Codex 的差别：Kimi 更像“可脚本化 CLI agent”，但不是 Paperclip 一等 adapter

Claude 和 Codex 在 Paperclip 里有内置 `claude_local` / `codex_local` adapter。KimiCode 当前更适合两种接法：

```markdown
方案 A：Paperclip HTTP adapter → 你自写 kimi-runner service
方案 B：如果你当前 Paperclip 版本支持 generic process，则 process adapter → kimi --print
```

但我要强调一个细节：Paperclip 文档前面说有 Generic Process，后面又写 “Generic process adapter for custom CLI tools not yet implemented in V1”，这说明你本地版本必须实测。稳妥做法是先用 HTTP wrapper 包一层 Kimi。 [Paperclip AI+1](https://paperclipai-paperclip.mintlify.app/agents/process-adapter)

Kimi Code CLI 官方文档显示，它可以读写代码、执行 shell、搜索和抓网页，并能自动规划和调整；它支持 interactive CLI、browser UI、以及 `kimi acp` 这种 agent integration 模式。 [Kimi](https://www.kimi.com/code/docs/en/kimi-code-cli/getting-started.html)

Kimi 的 `--print` 模式适合被脚本调用：可以通过 `-p` 或 stdin 传 prompt，执行完自动退出，也支持 stream-json 输入输出。 [Moonshot AI](https://moonshotai.github.io/kimi-cli/en/customization/print-mode.html)

但这里有一个高风险点：Kimi `--print` 模式文档明确说它是 non-interactive，并且会隐式启用 `--yolo` ，所有操作自动批准。 [Moonshot AI](https://moonshotai.github.io/kimi-cli/en/customization/print-mode.html)

所以 KimiCode 直接作为 Paperclip runtime 时，我不会让它自由跑：

```markdown
kimi --print --yolo 在你的真实项目根目录
```

我会让它跑在：

```markdown
Docker sandbox
只读 data/docs
只写 outputs
无真实 token
无 ~/.ssh
无 ~/.aws
无生产项目目录
```

并且用 custom agent file 限制工具。例如 Kimi agent 文件可以 `extend: default` ，再 `exclude_tools` 去掉 Shell / WriteFile / FetchURL 等。Kimi 文档显示自定义 agent YAML 可以继承默认 agent，并通过 `exclude_tools` 排除工具。 [Moonshot AI](https://moonshotai.github.io/kimi-cli/en/customization/agents.html)

---

## 5\. 三个 runtime 应该怎么分工？

不要让 ClaudeCode、KimiCode、Codex 三个 agent 都做同一件事。那会互相覆盖、重复消耗、产物冲突。

我建议这样分工：

| Runtime | 在 Paperclip 里的角色 | 最适合任务 | 不适合任务 |
| --- | --- | --- | --- |
| **ClaudeCode** | Product Innovation Director / Design Director / Boss Memo | 长文综合、产品策略、审美判断、设计 brief、老板讲稿、风险解释 | 大规模代码重构、重复数据脚本、严格 JSON pipeline |
| **Codex** | Frontend Engineer / Workflow Engineer / Data Tooling Engineer | React 页面、LangGraph 代码、数据脚本、测试、schema、CI、修 bug | 高审美品牌判断、模糊产品战略 |
| **KimiCode** | Competitive Radar / Chinese-English Research / Reference Library Agent | 长上下文资料消化、竞品调研、中文资料综合、设计参考拆解、快速网页/文档分析 | 直接写生产文件、无限制 shell、真实账号操作 |
| **LangGraph/DeepAgents** | 隐藏执行流水线 | VOC→机会→人审→设计→DFM→资产矩阵这种固定流程 | 老板可视化组织图、AI 公司管理感 |
| **Paperclip** | 控制台 / 管理层 / 审批台 | org chart、issue tree、budget、heartbeat、activity log、boss demo | 强类型状态机、最终 CAD、安全认证、真实发布 |

这套分工非常重要。  
如果你把三种 runtime 都配置成：

```markdown
你是 Labebe AI Agent，请完成 Demo
```

最后会变成：

```markdown
三个 agent 都在写大作文
都在改同一批文件
都在生成不一致的数据
都在声称自己完成了全流程
```

世界级 Demo 会变乱。

---

## 6\. 直接 Paperclip + 三 runtime 和 LangGraph/DeepAgents 的核心对比

## 6.1 总表

| 维度 | Paperclip 直接挂 Claude/Kimi/Codex | Paperclip + LangGraph/DeepAgents |
| --- | --- | --- |
| 启动速度 | 很快 | 慢一些 |
| 老板演示观感 | 很强，像 AI 公司 | 需要自己做 UI |
| Agent Team 展示 | 极强 | 中等 |
| 长流程稳定性 | 中等，靠 prompt 和 Issue 纪律 | 强，靠 graph state |
| 人审中断 | Issue / approval 级别 | node / state 级别 |
| 可恢复执行 | CLI session resume | checkpoint / thread\_id |
| 输出结构化 | 靠 prompt | schema / state 原生 |
| 工程可测试 | 较弱 | 强 |
| Demo 现场稳定性 | 需要预生成兜底 | 更容易稳定 |
| 真实生产化 | 需要加很多 wrapper | 更适合生产 |
| 安全边界 | 高风险，尤其 headless / yolo / bypass | 也有风险，但更容易集中封装 |
| 多模型并行 | 容易 | 需要工程设计 |
| 适合任务 | 开放式设计、代码、文档、演示 | 固定业务流程、审批、可恢复管线 |

---

## 6.2 本质区别一句话

```markdown
Paperclip 直接挂 runtime：
“我雇了三个很厉害的 AI 员工，让他们按任务推进。”

Paperclip + LangGraph：
“我设计了一条产品创新流水线，每个节点可以调用不同 AI 专家，但流程由系统控制。”

Paperclip + LangGraph + Claude/Kimi/Codex：
“我既有 AI 公司作战室，也有真实可重复执行的产品创新流水线。”
```

---

## 7\. 直接 Paperclip runtime 方案最容易翻车的地方

## 7.1 权限和安全

Claude Code 自己支持权限规则和 permission modes；Anthropic 也在 2026 年 3 月介绍了 Claude Code auto mode，目标是在手动批准和完全跳过权限之间做折中，因为 `--dangerously-skip-permissions` 在多数场景下不安全。 [Anthropic](https://www.anthropic.com/engineering/claude-code-auto-mode)

Codex 官方文档也说明，Codex CLI / IDE 默认使用 OS-level sandbox，通常网络关闭、写权限限制在工作区；它把 security controls 分成 sandbox mode 和 approval policy 两层。 [OpenAI Developers](https://developers.openai.com/codex/agent-approvals-security)

但 Paperclip 的 headless 执行会诱导你打开：

```markdown
dangerouslySkipPermissions
dangerouslyBypassApprovalsAndSandbox
kimi --print / --yolo
```

OpenAI Codex CLI 文档对 `--dangerously-bypass-approvals-and-sandbox` 的描述也很直接：绕过 approval prompts 和 sandboxing，只有在隔离 runner 里才应该用。 [OpenAI Developers](https://developers.openai.com/codex/cli/reference)

所以我建议：

```markdown
不要在你的主机真实项目目录里直接跑 full-permission agent。
不要把真实 Shopify / Amazon / Gmail / Meta / TikTok token 放进这些 runtime。
不要把 ~/.ssh、~/.aws、~/Documents 暴露给 Paperclip workspace。
```

Paperclip 自己的安全页面近期也列出过多条 advisory，包括 unauthenticated RCE、cross-tenant token、Gmail 继承权限、任意文件读取、恶意 skills 外泄数据等。 [GitHub](https://github.com/paperclipai/paperclip/security/advisories)  
其中一个 RCE advisory 明确写到，受影响版本 `< 2026.416.0` ，patched version 是 `2026.416.0` ，并描述了默认 authenticated mode 下网络可访问实例可能被未认证攻击者远程代码执行。 [GitHub](https://github.com/paperclipai/paperclip/security/advisories/GHSA-68qg-g8mg-6pr7)

因此，直接 runtime 方案必须遵守：

```markdown
local only
127.0.0.1 only
latest patched version
sandbox workspace only
no real external write tokens
no production credentials
```

---

## 7.2 三套 skill / instruction 系统会打架

你会同时遇到：

```markdown
Paperclip skills
Claude CLAUDE.md / skills
Codex AGENTS.md / CODEX_HOME skills
Kimi AGENTS.md / skills
Labebe DESIGN.md
Labebe DATA_TRUTH.md
```

Kimi 文档显示，它会分层发现 skills：Project > User > Extra > Built-in；并且默认会合并 `.kimi/skills` 、`.claude/skills` 、`.codex/skills` 等 brand directories，优先级 kimi > claude > codex。 [Moonshot AI](https://moonshotai.github.io/kimi-cli/en/customization/skills.html)

这很强，但也会出问题：

```markdown
Claude 读一套规则
Codex 读一套规则
Kimi 又合并几套规则
Paperclip 再注入自己的 skill
```

如果你不统一设计规则，很容易出现：

```markdown
Claude 说 Pink Unicorn 是 $109.99
Kimi 生成 $89.99
Codex 前端写死 247 reviews
Paperclip issue 里又说 review count unknown
```

所以必须建立单一规则源：

```markdown
docs/DATA_TRUTH.md
docs/DESIGN.md
docs/FORBIDDEN_CLAIMS.md
docs/ACTION_POLICY.md
```

并且三套 runtime 都只引用这些文件，不允许各自编数据。

---

## 7.3 Cross-agent handoff 可能带来 prompt injection

Paperclip 社区 issue 已经有人指出，agent A 的输出可能作为 session handoff 进入 agent B 的 prompt，如果这个内容没有清晰标记为 untrusted previous output，就可能形成跨 agent prompt injection。 [GitHub](https://github.com/paperclipai/paperclip/issues/2755?utm_source=chatgpt.com)

对 Labebe 来说，这个风险尤其实际，因为你会处理：

```markdown
竞品网页
Amazon 评论
TikTok 文案
外部网页
Kimi 抓取结果
AI 生成 prompt
```

这些都是不可信输入。

所以直接 runtime 方案里必须规定：

```markdown
所有外部网页 / 评论 / 竞品内容都标记为 untrusted source。
所有 agent output 只能作为 context，不能作为 instruction。
跨 agent handoff 必须走结构化 summary，不要整段自由文本互相喂。
```

这也是我倾向最终把关键流程放进 LangGraph 的原因：你可以把输入边界、schema、review gate 做得更硬。

---

## 8\. 直接 Paperclip runtime 能不能完成你想要的所有 Demo？

可以，但不同 Demo 的可靠度不同。

## 8.1 高度适合直接 Paperclip runtime 的 Demo

这些非常适合：

```markdown
AI Design Agent Team War Room
Design Opportunity Radar 初版
VOC → Design Brief
Design Director Scorecard
DFM / Safety Preflight 文档
Concept-to-Market Asset Matrix
Boss Demo Script
Design Library / Reference Map
前端页面搭建
短视频分镜
```

原因：

```markdown
这些主要是研究、综合、写作、代码、文档、轻结构产物。
Claude / Kimi / Codex 都很擅长。
Paperclip 的 Issue / Comment / Approval 足够支撑演示。
```

## 8.2 可以做，但需要 wrapper 的 Demo

这些不建议让 agent 自由发挥：

```markdown
竞品大数据爬取
评论聚类
销量数据分析
产品机会打分
多渠道资产矩阵 JSON
图片生成批处理
视频脚本批处理
前端读取 outputs 渲染
```

应该让 Codex 写脚本，agent 调脚本：

```markdown
scripts/voc_cluster.py
scripts/opportunity_radar.py
scripts/design_scorecard.py
scripts/asset_matrix.py
scripts/render_demo_outputs.py
```

Paperclip agent 负责解释和推进，不负责凭感觉算结果。

## 8.3 不适合直接 Paperclip runtime 的 Demo

这些不要交给 Claude/Kimi/Codex 直接做：

```markdown
真实 CAD 生产图
真实安全认证判断
真实 Shopify 改价
真实 Amazon / Meta / TikTok 发布
真实 Gmail 外发
真实客户数据处理
真实广告预算操作
```

只能做：

```markdown
concept render
CAD direction brief
DFM preflight
human review packet
launch-test asset draft
```

---

## 9\. 我建议的实际架构：先 Paperclip-only，再升级 hybrid

## 阶段 1：Paperclip + ClaudeCode/KimiCode/Codex，快速出世界级 Demo

目标：

```markdown
3–7 天做出老板可看的 AI Design Studio 作战室。
```

架构：

```markdown
Paperclip
  ├── ClaudeCode: CEO / Design Director / Demo Producer
  ├── Codex: Frontend Engineer / Data Script Engineer
  └── KimiCode: Competitive Radar / Reference Library / Long-context Research
```

输出：

```markdown
docs/DESIGN.md
docs/DATA_TRUTH.md
outputs/opportunity_radar.md
outputs/spacesmart_learning_tower_brief.md
outputs/design_scorecard.md
outputs/dfm_safety_preflight.md
outputs/asset_matrix.md
frontend/AI Design Studio Demo
90s video script
15min boss demo path
```

这个阶段的关键不是“全部自动化”，而是：

```markdown
用 Paperclip 展示 AI 团队怎么协作；
用 runtime 真实生成一批高质量产物；
用前端把产物包装成世界级 Demo。
```

---

## 阶段 2：Paperclip + wrapper scripts，把关键输出结构化

目标：

```markdown
把开放式 agent 输出变成可控 outputs。
```

加入：

```markdown
scripts/paperclip_runner.py
scripts/voc_to_design.py
scripts/opportunity_radar.py
scripts/dfm_preflight.py
scripts/asset_matrix.py
```

流程：

```markdown
Paperclip Issue
  ↓
Claude/Kimi/Codex 读取任务
  ↓
调用固定 script
  ↓
script 输出 JSON/Markdown
  ↓
agent 解释结果并更新 issue
```

这个阶段已经能解决很多问题：

```markdown
不再靠 agent 自己算所有结果
输出结构稳定
前端可读取
Demo 可重复
```

---

## 阶段 3：Paperclip + LangGraph + DeepAgents，做真实产品创新系统

目标：

```markdown
把 Labebe AI Design Studio 从演示升级成可长期运行的产品创新管线。
```

最终架构：

```markdown
Paperclip Control Plane
  ├── AI company dashboard
  ├── agents / org chart
  ├── issues
  ├── approvals
  ├── budgets
  └── activity log

LangGraph Runtime
  ├── truth_base_load
  ├── voc_analysis
  ├── competitor_radar
  ├── opportunity_synthesis
  ├── human approval interrupt
  ├── design_brief
  ├── design_director_score
  ├── dfm_preflight
  ├── human approval interrupt
  └── asset_matrix

DeepAgents / Claude / Kimi / Codex
  └── 被 LangGraph 节点调用为专家能力

Frontend
  └── Labebe AI Design Studio visual demo
```

DeepAgents 很适合作为 LangGraph 节点里的“复杂专家 agent”：DeepAgents 项目说明它是基于 LangChain / LangGraph 的 agent harness，带 planning tool、filesystem backend、subagents，适合复杂 agentic tasks；但它自己的安全说明也强调是 “trust the LLM”，agent 能做任何工具允许的事，边界必须由工具或 sandbox enforcing。 [GitHub](https://github.com/langchain-ai/deepagents)

JavaScript 版 DeepAgents 也写明 `createDeepAgent` 返回 compiled LangGraph graph，可以用 streaming、Studio、checkpointers 等 LangGraph 能力。 [GitHub](https://github.com/langchain-ai/deepagentsjs)

所以最终最稳的是：

```markdown
Paperclip 管“谁、任务、审批、日志”
LangGraph 管“流程状态和中断”
DeepAgents / Claude / Kimi / Codex 管“复杂脑力活”
```

---

## 10\. 推荐的 Paperclip runtime 分配表

## 10.1 第一版就这样配

| Paperclip Agent | Runtime | Adapter 方式 | 说明 |
| --- | --- | --- | --- |
| Product Innovation Director | ClaudeCode | `claude_local` | 总控、拆任务、老板汇总、审批请求 |
| Design Director Agent | ClaudeCode | `claude_local` | 审美评分、品牌一致性、prompt 改写 |
| Demo Producer Agent | ClaudeCode | `claude_local` | 90 秒视频、15 分钟老板讲稿 |
| Frontend Engineer Agent | Codex | `codex_local` | React / Next 页面、数据结构、修 bug |
| Workflow Engineer Agent | Codex | `codex_local` | LangGraph / scripts / schema / tests |
| Competitive Radar Agent | KimiCode | HTTP wrapper 或 process | 长上下文竞品、中文/英文资料、参考拆解 |
| Data Truth Guard | Codex 或 Python script | `codex_local` / wrapper | 校验产品数据和禁止 claim |
| VOC Analyst | Claude 或 Kimi | Claude for synthesis, Kimi for bulk research | 评论和痛点到设计要求 |

---

## 10.2 不建议这样配

```markdown
CEO = Claude
VOC = Claude
Competitor = Claude
Design = Claude
DFM = Claude
GTM = Claude
Frontend = Claude
Research = Claude
```

这样虽然简单，但你没有发挥 Codex/Kimi 的差异化。

也不建议：

```markdown
三个 runtime 都能改所有文件
三个 runtime 都能访问所有数据
三个 runtime 都能跑 shell
三个 runtime 都能写 frontend
```

这会导致：

```markdown
产物冲突
文件互相覆盖
数据口径不一致
agent 互相污染上下文
```

---

## 11\. 配置建议：ClaudeCode

Paperclip Claude agent 可以这样配：

```markdown
{
  "adapterType": "claude_local",
  "adapterConfig": {
    "command": "claude",
    "cwd": "/absolute/path/to/labebe-ai-design-studio/workspace",
    "instructionsFilePath": "/absolute/path/to/labebe-ai-design-studio/agents/product_innovation_director.md",
    "model": "claude-sonnet-4-6",
    "effort": "high",
    "maxTurnsPerRun": 80,
    "promptTemplate": "You are {{agent.name}} in Labebe AI Design Studio. Continue the assigned Paperclip issue. Use DATA_TRUTH.md and DESIGN.md before making claims.",
    "timeoutSec": 1800,
    "graceSec": 30,
    "env": {
      "ANTHROPIC_API_KEY": "${secrets.anthropic_key}"
    }
  },
  "contextMode": "fat",
  "budgetMonthlyCents": 1500
}
```

我的建议：

```markdown
CEO / Design Director 用 ClaudeCode。
不要让 ClaudeCode 直接做 unrestricted shell。
它最适合策略、审美、综合、讲稿、评审。
```

如果你为了 headless 自动化不得不开权限，必须放在隔离 workspace 或 Docker 里。Claude 官方也明确强调 Claude Code 能读文件、跑命令、改文件并自主工作，但同时上下文会快速填满，需要管理 context、写有效 CLAUDE.md、探索-计划-实现、用 subagents 调查、积极纠偏。 [Claude](https://code.claude.com/docs/en/best-practices)

---

## 12\. 配置建议：Codex

Codex 适合工程任务：

```markdown
{
  "adapterType": "codex_local",
  "adapterConfig": {
    "command": "codex",
    "cwd": "/absolute/path/to/labebe-ai-design-studio",
    "instructionsFilePath": "/absolute/path/to/labebe-ai-design-studio/agents/frontend_engineer.md",
    "model": "gpt-5.3-codex",
    "modelReasoningEffort": "high",
    "search": false,
    "promptTemplate": "You are {{agent.name}}. Implement only the assigned issue. Follow AGENTS.md, DESIGN.md, DATA_TRUTH.md, and run tests before reporting done.",
    "dangerouslyBypassApprovalsAndSandbox": false,
    "timeoutSec": 1800,
    "graceSec": 20,
    "env": {
      "OPENAI_API_KEY": "${secrets.openai_key}"
    }
  },
  "contextMode": "thin",
  "budgetMonthlyCents": 2000
}
```

但要注意：Codex CLI 官方把 sandbox 和 approval 分成两层，默认网络关闭，写权限通常限制在 workspace；如果你用 bypass flag，就等于绕开 approval 和 sandbox，只应在外部加固环境里用。 [OpenAI Developers+1](https://developers.openai.com/codex/agent-approvals-security)

我的建议：

```markdown
Codex 负责：
- 前端页面
- 数据 schema
- scripts
- LangGraph workflow
- 测试
- 修路由
- 性能修复

不要让 Codex 负责：
- 审美总监
- 老板战略判断
- 产品 claim
- 真实外部账号操作
```

---

## 13\. 配置建议：KimiCode

KimiCode 我建议不要第一版直接塞进 `claude_local/codex_local` 这种内置 adapter；应该做一个 wrapper。

## 13.1 最稳：HTTP wrapper

```markdown
Paperclip HTTP Adapter
  ↓
http://127.0.0.1:8788/paperclip/kimi-run
  ↓
kimi --print --output-format=stream-json --agent-file ...
  ↓
parse output
  ↓
return summary + artifact paths
```

Paperclip 里配置：

```markdown
{
  "adapterType": "http",
  "adapterConfig": {
    "url": "http://127.0.0.1:8788/paperclip/kimi-run",
    "method": "POST",
    "timeoutMs": 900000,
    "headers": {
      "Authorization": "Bearer ${secrets.labebe_local_runner_key}"
    }
  }
}
```

kimi-runner 内部执行：

```markdown
kimi \
  --print \
  --output-format=stream-json \
  --agent-file /workspace/agents/kimi_competitive_radar.yaml \
  --work-dir /workspace \
  --max-steps-per-turn 40 \
  -p "$PROMPT"
```

这样做的好处：

```markdown
1. 你能统一控制 workspace。
2. 你能解析 Kimi JSONL 输出。
3. 你能把 exit code 75 当 transient retry。
4. 你能把 Kimi session export 保存为 artifact。
5. 你能在 Docker 里跑 Kimi，限制读写。
6. Paperclip 不需要知道 Kimi 内部协议。
```

Kimi print mode 支持 JSONL 输入输出和 exit code，exit code `75` 表示 retryable transient error，适合 wrapper 做重试。 [Moonshot AI](https://moonshotai.github.io/kimi-cli/en/customization/print-mode.html)

## 13.2 Kimi custom agent 文件

```markdown
version: 1
agent:
  extend: default
  name: labebe-competitive-radar
  system_prompt_path: ./kimi_competitive_radar.md
  exclude_tools:
    - "kimi_cli.tools.file:WriteFile"
    - "kimi_cli.tools.file:StrReplaceFile"
    - "kimi_cli.tools.shell:Shell"
```

研究型 Kimi agent 我建议先禁写、禁 shell，只保留读文件、搜索、抓网页。Kimi 文档里列出的默认工具包括 Shell、ReadFile、WriteFile、SearchWeb、FetchURL、Agent 等；自定义 agent 支持 `exclude_tools` 。 [Moonshot AI](https://moonshotai.github.io/kimi-cli/en/customization/agents.html)

---

## 14\. 直接 runtime 方案下，Demo 应该怎么组织？

## 14.1 Paperclip Issue Tree

```markdown
EPIC 0 — Data Truth Foundation
  0.1 Build DATA_TRUTH.md
  0.2 Freeze product seed
  0.3 Remove fake prices / reviews / ratings

EPIC 1 — Design Opportunity Radar
  1.1 VOC signals
  1.2 Competitor matrix
  1.3 Opportunity scoring
  1.4 Human approval

EPIC 2 — VOC to Product Concept
  2.1 Learning Tower pain clusters
  2.2 SpaceSmart brief
  2.3 Design requirements JSON
  2.4 Approval

EPIC 3 — Sketch-to-Concept
  3.1 Four design routes
  3.2 Prompt pack
  3.3 Concept image plan
  3.4 Design Director score

EPIC 4 — Custom Toy Kitchen Builder
  4.1 Module schema
  4.2 Frontend interaction
  4.3 Concept output
  4.4 Waitlist block

EPIC 5 — DFM / Safety Preflight
  5.1 Risk checklist
  5.2 Engineering review packet
  5.3 Forbidden claims

EPIC 6 — Concept-to-Market Asset Matrix
  6.1 PDP module
  6.2 Amazon A+
  6.3 TikTok scripts
  6.4 Meta carousel
  6.5 Email / waitlist

EPIC 7 — Boss Demo Production
  7.1 90-second video
  7.2 15-minute talk track
  7.3 Paperclip dashboard recording
```

## 14.2 Agent 分配

```markdown
Claude CEO:
EPIC 1 / 2 / 7 总控

Kimi Competitive Radar:
EPIC 1 竞品和参考研究

Codex Frontend:
EPIC 4 前端 / AI Studio 页面

Claude Design Director:
EPIC 3 / 5 审美与风险解释

Codex Workflow Engineer:
scripts / outputs / JSON schema

Claude Demo Producer:
短视频和老板讲稿
```

---

## 15\. 但关键流程不要长期放在 agent 自由发挥里

我建议你第一版可以直接 Paperclip + runtimes 迅速做出来。  
但长期必须把下面这些做成确定性 workflow：

```markdown
truth check
VOC clustering
opportunity scoring
human approval
design brief JSON
design score JSON
DFM preflight JSON
asset matrix JSON
```

原因很简单：

```markdown
这些是 Labebe AI Design Studio 的核心资产。
它们不能每次靠 agent 大作文临场发挥。
```

所以最终我建议：

```markdown
Paperclip issue: Run Design Opportunity Radar
  ↓
Codex/Claude agent: 调用 scripts/run_opportunity_radar.py 或 LangGraph service
  ↓
LangGraph / script: 生成 outputs/opportunity_radar.json
  ↓
Claude agent: 解释结果，写老板版总结
  ↓
Paperclip: 进入 approval
```

这样你同时得到：

```markdown
结构化可信产物
+ Paperclip 的 AI 团队演示效果
```

---

## 16\. 最推荐的混合形态

我会这样搭：

```markdown
Paperclip
  ├── Claude Product Innovation Director
  │     负责老板可读总结、拆任务、审批请求
  │
  ├── Kimi Competitive Radar
  │     负责研究资料、竞品、参考拆解
  │
  ├── Codex Workflow Engineer
  │     负责 scripts / LangGraph / JSON / frontend
  │
  ├── Claude Design Director
  │     负责审美、品牌、prompt、设计评分
  │
  └── Codex Frontend Engineer
        负责 Labebe AI Design Studio 页面

LangGraph service
  ├── load_truth_base
  ├── voc_analysis
  ├── competitor_radar
  ├── opportunity_synthesis
  ├── approval_interrupt
  ├── design_brief
  ├── design_director_score
  ├── dfm_preflight
  ├── approval_interrupt
  └── asset_matrix

Frontend
  ├── Opportunity Radar
  ├── Agent War Room
  ├── Sketch-to-Concept
  ├── Custom Toy Kitchen Builder
  ├── Design Director Scorecard
  ├── DFM Preflight
  └── Concept-to-Market Matrix
```

这套才是我认为最强的。

---

## 17\. 什么情况下只用 Paperclip + runtimes 就够了？

如果你的目标是：

```markdown
7 天内做一个老板演示
90 秒短视频
15 分钟现场讲解
展示 AI Team 头脑风暴
展示几个输出文件
展示一个前端 Demo
```

那只用 Paperclip + ClaudeCode + Codex + KimiCode 就够了。

只要你加好：

```markdown
DATA_TRUTH.md
DESIGN.md
ACTION_POLICY.md
FORBIDDEN_CLAIMS.md
sandbox workspace
pre-generated assets
fallback screenshots
```

就可以做得很惊艳。

---

## 18\. 什么情况下必须加 LangGraph？

如果你要做到：

```markdown
每周自动跑 VOC
自动读取竞品样本
自动生成机会雷达
每个机会固定评分
人审后自动进入概念生成
自动生成 JSON 给前端
失败后可恢复
每一步可重放
同一流程可运行 100 次
```

就必须加 LangGraph。

因为 LangGraph 的 durable execution 原生就是为长流程、失败恢复、人审中断设计的；文档明确说它可以保存进度、暂停后恢复、避免重复已完成步骤，并依赖 checkpointer 和 thread\_id 跟踪执行历史。 [LangChain Docs](https://docs.langchain.com/oss/python/langgraph/durable-execution)

---

## 19\. 我给你的最终方案选择

## 最快世界级 Demo

```markdown
Paperclip
+ ClaudeCode
+ Codex
+ KimiCode via HTTP wrapper
+ 结构化 scripts
+ 独立 Labebe AI Design Studio 前端
```

这是你现在最该做的版本。

## 最稳长期系统

```markdown
Paperclip
+ LangGraph service
+ DeepAgents / Claude / Codex / Kimi as node-level specialists
+ Postgres checkpoint
+ outputs JSON
+ frontend
```

这是第二阶段。

## 不推荐

```markdown
Paperclip
+ 三个 runtime 全权限自由跑
+ 没有 scripts
+ 没有 DATA_TRUTH
+ 没有 schema
+ 没有 sandbox
+ 没有 approval gates
```

这会很热闹，但容易失控。

---

## 20\. 最终一句话

直接给 Paperclip 配 ClaudeCode、KimiCode、Codex，和 Paperclip + LangGraph/DeepAgents 的区别是：

```markdown
前者是“雇一群强 AI 员工，让他们自己推进任务”；
后者是“设计一条可恢复、可审批、可验证的产品创新流水线，让 AI 专家在每个节点工作”。
```

对 Labebe，我建议：

```markdown
先用 Paperclip + ClaudeCode / Codex / KimiCode 做出世界级 AI Design Studio 作战室；
再把 VOC→机会→设计→DFM→资产矩阵这条主链路固化成 LangGraph；
最后让 Paperclip 负责老板看得懂的组织、任务、预算、审批和日志。
```

这样你既能快速拿出震撼 Demo，又不会把核心能力建在“agent 自己发挥”的不稳定地基上。