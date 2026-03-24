## 目标

在不引入多个常驻 OpenClaw research agent 的前提下，把 `finbot` 的机会深挖从：

- 单线性 `brief -> dossier`

升级为：

- `claim lane`
- `skeptic lane`
- `expression lane`
- `decision lane`

并确认这套结构：

1. 能写入 live artifact
2. 能进入 investor dashboard
3. 能以投资人可消费的形式展示出来

## 代码改动

### 1. `chatgptrest/finbot.py`

补了内部 lane 化机会深挖：

- `_ask_coding_plan_lane(...)`
- `_build_claim_lane_prompt(...)`
- `_build_skeptic_lane_prompt(...)`
- `_build_expression_lane_prompt(...)`
- `_build_decision_lane_prompt(...)`
- `_compose_lane_markdown(...)`
- `_compose_research_package_markdown(...)`
- `_write_lane_artifacts(...)`

并将 `opportunity_deepen(...)` 改成：

1. 读 candidate / theme / source / dossier 上下文
2. 先跑：
   - `claim`
   - `skeptic`
   - `expression`
3. 再跑 `decision`
4. 把结果写入：
   - `history/<ts>/research_package.json`
   - `history/<ts>/research_package.md`
   - `history/<ts>/lanes/*.json`
   - `history/<ts>/lanes/*.md`
5. 更新：
   - `latest.json`
   - `latest.md`
   - `latest_context.json`

### 2. Investor opportunity detail 模板

更新：

- `chatgptrest/dashboard/templates/investor_opportunity_detail.html`

新增展示区块：

- `Claim Lane`
- `Skeptic Lane`
- `Expression Lane`

### 3. 测试

更新：

- `tests/test_finbot.py`
- `tests/test_dashboard_routes.py`

新增断言：

- dossier payload 带 `lanes`
- investor detail 页面能看到 3 个 lane 标题

## 测试回归

本轮定向测试：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/pytest -q \
  tests/test_finbot.py \
  tests/test_dashboard_routes.py \
  tests/test_executor_factory.py \
  tests/test_coding_plan_executor.py
```

结果：通过。

## live 问题与修复

### 问题

最初 live 页面没有显示 lane，不是模板没改，而是 **端口 18711 被旧 worktree 的手工 python 进程占着**：

- 旧进程 cwd：
  - `/vol1/1000/projects/ChatgptREST/.worktrees/runtime-feature-memory`

这导致：

- `systemd` 服务在重启
- 但实际对外提供流量的是旧进程
- 所以页面一直显示旧代码

### 修复

1. 停掉旧占端口进程
2. 用 `chatgptrest.cli service restart` 重启 `chatgptrest-api.service`
3. 确认新的 managed 进程 cwd 指向：
   - `/vol1/1000/worktrees/chatgptrest-finbot-runtime-20260316`

## live 验证

### 1. 真实 deepening 产物

执行：

```bash
PYTHONPATH=. /vol1/1000/projects/ChatgptREST/.venv/bin/python \
  ops/openclaw_finbot.py opportunity-deepen \
  --format json \
  --candidate-id candidate_tsmc_cpo_cpo_d519030bd1 \
  --force
```

随后校验：

- `artifacts/finbot/opportunities/tsmc-cpo-cpo-d519030bd1/latest.json`

结果：

- `lanes = ["claim", "expression", "skeptic"]`
- `current_decision = "not_yet_investable"`

### 2. live investor 页面

访问：

- `/v2/dashboard/investor/opportunities/candidate_tsmc_cpo_cpo_d519030bd1`

确认已出现：

- `Claim Lane`
- `Skeptic Lane`
- `Expression Lane`

并能看到：

- `中际旭创800G/1.6T光模块`
- skeptic bear case
- claim lane core claims

## 当前结果的真实评价

这一版已经完成了“多 lane 原型”的核心闭环：

- lane 真实运行
- lane artifact 真实落盘
- dashboard 真实展示

但它仍然只是 **prototype**，还不是终局：

- `claim` 仍偏 narrative summary，不是完整 claim ledger
- `skeptic` 仍依赖单轮提示词质量
- `expression` 还没有正式接 valuation / scenario layer

## 结论

这轮验证说明：

**`single ingress + single finbot + internal lanes` 不是纸面架构，而是已经在 live 环境里跑通的原型。**

下一阶段最值得继续做的是：

1. claim ledger 结构化
2. skeptic evidence grading
3. expression comparison 的估值与情景层
4. decision lane 的强制事件与 posture discipline
