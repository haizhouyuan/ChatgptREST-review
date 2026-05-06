# Codex 跨系统审计核验修正版 v2

**日期**: 2026-03-12  
**范围**: ChatgptREST / OpenMind / OpenClaw / Feishu 协作面 / FinAgent  
**方法**: 代码精读、GitNexus 索引核对、运行态 API 摘要、FinAgent CLI 实测、现有审查文档复核

---

## 本版目的

本版用于修正无版本旧稿 `2026-03-12_codex_cross_system_audit_verification.md` 中的关键核验偏差，并把跨系统问题重新整理为“业务流程完整度 + 产品可交付性 + 结构调整优先级”三个维度的统一结论。

---

## 对旧稿的关键修正

### 1. FinAgent 不是“全空 DB”

旧稿把 FinAgent 判成 “28 表全空，MVP 不存在”。这条结论不成立。

本轮直接运行 `python3 -m finagent.cli --root /vol1/1000/projects/finagent today-cockpit`，返回的真实摘要包括：

- `artifacts = 118`
- `claims = 5341`
- `themes = 4`
- `theses = 2`
- `target_cases = 10`
- `validation_cases = 38`
- `operator_decisions = 0`
- `reviews = 0`
- `timing_plans = 0`

这说明 FinAgent 的真实问题不是“没有数据”，而是“数据与研究资产已经积累，但尚未闭环到 operator decision / review / timing plan”。

### 2. FinAgent 的主问题应是“决策闭环缺失”，不是“基础链路不存在”

旧稿把 FinAgent 定性为“整条链路从未跑通”，这个结论过重。当前更准确的判断是：

- intake / artifact / claim / route / thesis / target case 这一段已经跑通
- operator review / decision / timing plan / action 这一段还没有形成强约束闭环

因此 FinAgent 的优先级仍然很高，但重点应放在“决策工作流补齐”和“结构拆层”，而不是从零重建数据链路。

---

## 核验后的优先级结论

### P0-1: OpenClaw / OpenMind 的 agent runtime 没有真正闭环

关键证据：

- `AdvisorOrchestrateExecutor.run()` 主要负责拼装和创建 child job，而不是统一承接执行、守护、修复的 runtime 状态机
- `OpenClawAdapter.run_protocol()` 只做 `spawn -> send -> status` 的薄封装
- guardian / incident / wake 仍在独立脚本和独立运维面

业务影响：

- handoff、repair、incident 不在一个统一生命周期里
- 系统的“多 agent 能力”被削弱成“thin adapter + 外部守护脚本”
- 故障治理仍主要靠脚本和巡检，而不是 runtime 自身吸收

### P0-2: 运行态健康口径偏乐观，稳定交付还不够

本轮运行态摘要显示：

- `active_incidents = 30`
- `active_open_issues = 16`
- `stuck_wait_jobs = 4`
- `ui_canary_ok = true`

这意味着：

- 健康检查“探针正常”不等于“系统稳定可交付”
- stuck wait / no progress / no thread url 仍是主要不稳定源
- provider 级熔断、重试、收口策略还不够成体系

### P1-3: Feishu 仍是消息入口，不是完整协作产品面

核验结果显示：

- webhook 卡片链路存在
- Feishu WS 入口存在
- 附件目录、状态文件、scope 健康都做了

但缺失仍然明显：

- 没有统一的 Feishu ingress 边界
- webhook 与 WS 是两套并行路径
- 上下文同步、文档深链、工件回链、动作卡片、协作状态一致性没有形成完整产品面

### P1-4: FinAgent 的前门和当前数据面存在文档漂移

实测里，README 示例 `thesis_ai_infra` 已不能直接作为有效入口，`focus --thesis-id thesis_ai_infra` 返回 `thesis_not_found`。

### P1-5: FinAgent 的核心缺口是“研究资产到投资动作”的闭环没有建立

当前数据面已经有足够多的研究资产，但关键动作面仍为零：

- `operator_decisions = 0`
- `reviews = 0`
- `timing_plans = 0`

### P1-6: FinAgent 已进入明显结构债阶段

本轮核对到的几个信号：

- `views.py` 超大且承担了过多聚合职责
- `_load_context()` 读取范围过宽
- `cli.py` 仍是超大命令总控
- `db.py` 暴露的边界还偏原始

### P2-7: FinAgent 的 recurring ops 和质量判断仍偏硬编码

核对结果支持以下方向性判断：

- `daily-refresh` 仍偏 source-specific
- claim 提取、route 判定仍有明显 rule-based 特征

### P2-8: FinAgent 还是个人 CLI 工具形态，不是产品 runtime

当前更像：

- 单机 CLI
- 强本地路径 / 强环境绑定
- 人工驱动执行

而不是：

- daemon / API / scheduler 驱动
- 可部署、可观测、可多环境迁移
- 可被其他系统稳定调用

---

## 本版摘要

- OpenClaw/OpenMind 的首要问题是 runtime 统一性，而不是功能数量。
- ChatgptREST 的首要问题是稳定交付口径仍偏乐观。
- Feishu 的首要问题是协作面没有产品化。
- FinAgent 的首要问题是“研究资产到决策动作”的闭环缺失，而不是“完全没数据”。
- 旧稿中关于 FinAgent “全空 DB / MVP 不存在”的判断，应视为已被本版修正。
