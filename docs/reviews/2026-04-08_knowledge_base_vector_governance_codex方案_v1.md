# Knowledge Base / Vector Governance Codex方案 V1

Date: 2026-04-08

## 1. 结论先说

当前问题不是单点的“向量库没做好”，而是一个从入库到反馈的全链路治理问题：

1. 入库门禁过弱，垃圾与低复用 atom 持续进入。
2. promotion 调度虽已恢复，但吞吐和覆盖仍然很窄。
3. EvoMap、planning reviewed runtime pack、KB hybrid 三条知识面职责不清。
4. 默认热路径检索合同过窄，与真实用户 query 形态不匹配。
5. 用户反馈与质量回流几乎为空，系统无法持续自校正。

一句话冻结：

> 当前最该做的不是继续扩库或直接全量向量化，而是把知识系统治理成三条职责清晰的 knowledge plane，并补齐 ingestion → promotion → retrieval → feedback 的闭环。

## 2. 已核验的 live 事实

### 2.1 EvoMap 总体状态

来自 [evomap_knowledge.db](/vol1/1000/projects/ChatgptREST/data/evomap_knowledge.db)：

- `atoms_total = 104273`
- `promotion_status=staged = 102950`
- `promotion_status=candidate = 538`
- `promotion_status=active = 243`
- `planning_atoms = 36567`
- `planning active = 242`
- `planning staged = 35245`
- `planning groundedness = 0 = 36192`
- `planning groundedness >= 0.6 = 245`
- `planning quality_auto >= 0.7 and groundedness = 0 = 16647`
- `valid_from` 缺失 = `51429`
- `canonical_question` 缺失 = `47829`
- `chain_id` 非空 = `0`
- `status >= scored` 的 atoms = `3606`
- `groundedness_audit = 335`
- `promotion_audit = 1059`

### 2.2 反馈与遥测

来自同一 DB：

- `query_events = 403`
- `retrieval_events = 691`
- `answer_feedback = 0`

这说明遥测不是完全没有，但仍然太薄，反馈回路事实上是断开的。

### 2.3 KB / vector live 状态

来自 [kb_search.db](/home/yuanhaizhou/.openmind/kb_search.db)、[kb_vectors.db](/home/yuanhaizhou/.openmind/kb_vectors.db) 和 [kb_registry.db](/home/yuanhaizhou/.openmind/kb_registry.db)：

- `kb_fts = 941`
- `kb_fts_meta = 941`
- `kb_vectors = 151`
- `kb_registry.artifacts = 134`
- `kb_registry.artifacts.stability = draft: 134`
- `kb_registry.is_promoted = 0`
- `kb_fts_meta` 中 `source_path=''` 的条目 = `811 / 941`

这说明 KBHub 这条线不是没有内容，但 provenance 非常弱，registry 晋升也几乎没运行。

### 2.4 调度现实

当前 live user systemd 已有两条 timer：

- `chatgptrest-planning-bulk-promotion.timer`
- `chatgptrest-planning-review-maintenance.timer`

所以“完全没有调度”已经不是现状。更准确的说法是：

- 调度存在
- reviewed maintenance 与 planning-specific bulk promotion 已恢复
- 但 generic promotion throughput 仍明显不足

### 2.5 检索现实

1. [retrieval.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/retrieval.py) 的 `USER_HOT_PATH` 当前仍是 `active-only`。
2. [context_assembler.py](/vol1/1000/projects/ChatgptREST/chatgptrest/kernel/context_assembler.py) 默认走的就是这条 hot path。
3. 对真实 planning 查询，如：
   - `绿源 车身 项目 准备`
   - `钛虎机器人 关节模组 合作`
   - `行星滚柱丝杠 供应商 选择`
   在 EvoMap FTS 上直接空结果。
4. `.venv` 运行时的 KB probe 已证明向量命中是可用的，但命中主要落在泛 research/resource 文档，不是稳定的项目型知识。

## 3. 我对 Claude 方案的逐条判断

### 3.1 我同意的部分

1. “向量库问题只是冰山一角”这个判断是对的。
2. “垃圾入库无门禁”成立，而且是全链路问题的上游原因之一。
3. “两套知识系统割裂”成立，但准确说法应当是三条 plane 并存：
   - EvoMap promoted plane
   - planning reviewed runtime pack
   - KB hybrid evidence plane
4. “feedback loop 基本没接通”成立。
5. “链式演化与 supersession 几乎未运行”成立。

### 3.2 我不同意或要修正的部分

1. 不应再说“promotion timer 根本不存在”。
   这个判断已被当前 live 运行面推翻。

2. 不应把向量库现状概括成“完全没用”。
   更准确地说：
   - 普通 `python3` 路径下容易退成 FTS-only
   - `.venv` 服务运行时向量可用
   - 但 corpus 太薄、project-aware provenance 不足、命中质量偏泛

3. 不应直接把“先做 EvoMap 全量向量化”放到过高优先级。
   如果对象仍然脏、question 形态仍然错、promotion 仍然薄，那么全量向量化只是把脏对象编码进另一种索引。

4. 不应把问题表述成“两套系统必须尽快合并”。
   现阶段更合理的路径是先冻结职责边界，再逐步统一合同，而不是先做物理或逻辑合并。

## 4. 根因诊断

### 4.1 入库对象定义错位

当前有大量 atom 更像：

- 运行事件痕迹
- 长报告切片
- 通用结论碎片
- 命令/路径片段

而不是用户会问的问题单元。结果是：

- FTS 撞不上真实 query
- canonical question 缺失率高
- chain_builder 无法建立高质量演化链

### 4.2 source family 治理缺失

目前 promotion 与 groundedness 过于“统一化”。

但是 planning atom、code/procedure atom、event atom 的 groundedness 语义并不一样。  
对 planning atom 用同一套 code-symbol 权重，会误伤大量原本有价值的知识。

### 4.3 三条 knowledge plane 没有被冻结成产品合同

当前三条 plane 都存在，但没有明确：

- 哪些 source family 应进哪条 plane
- 哪条 plane 默认参与什么检索面
- 哪条 plane 可以直接注入 prompt
- 哪条 plane 只做 evidence

这会导致：

- pack 新鲜但默认热路径不吃
- KB 向量能命中但命中的不是项目知识
- EvoMap active 太少时，系统整体表现仍然很弱

### 4.4 反馈闭环不存在

没有 `answer_feedback`，就不知道：

- 哪些 atom 真帮助了任务完成
- 哪些 atom 命中了但没用
- 哪些 query 该补 alt questions
- 哪些 family 该 promotion 或 quarantine

## 5. 收敛后的治理方案

### Phase A：止血，先把系统继续变脏这件事停住

目标：

- 阻断低价值 atom 持续进入
- 对现有垃圾族做可逆归档

动作：

1. 给 [BaseExtractor](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/extractors/base.py) 增加统一门禁：
   - 最短 answer 长度
   - 通用标题黑名单
   - 路径黑名单：`.venv`、`node_modules`、`__pycache__`
   - content hash / family dedup
2. 对 [activity_extractor.py](/vol1/1000/projects/ChatgptREST/chatgptrest/evomap/knowledge/extractors/activity_extractor.py) 单独收紧：
   - 低信号 event type 不入库
   - `(event_type, repo, session)` 家族去重
   - 只保留高信号 closeout/commit/repair 类事件
3. 对已有垃圾族先 `archive`，不做物理删除：
   - `tool.completed`
   - `.venv` / 纯命令路径
   - 通用标题如 `结论` / `Test Results`

验收：

- 新一轮 ingest 后，上述垃圾族新增量接近 0
- 归档动作有 dry-run 报告与 family 级回滚能力

### Phase B：把 promotion 从“存在”治理成“有效”

目标：

- 提高 planning 知识进入 candidate / active 的速度
- 保留 groundedness 语义，不走 shortcut

动作：

1. 做 family-aware groundedness：
   - planning atom：降低或移除 `code_symbol` 权重
   - code/procedure atom：保留 `code_symbol` 校验
2. 先做 sample 批量 groundedness，再扩大覆盖：
   - `planning_review_pack`
   - `planning_latest_output`
   - `planning_outputs`
   - `planning_strategy`
3. 回填 `valid_from`
4. 补 canonical question / alt questions
5. 之后再运行 chain_builder，而不是在脏数据上先建链

验收：

- `groundedness_audit` 覆盖量显著增长
- planning `candidate + active` 有持续移动
- `chain_id_nonempty` 不再是 0
- `valid_from` 与 `canonical_question` 缺失率显著下降

### Phase C：冻结三条 knowledge plane 的职责

目标：

- 避免“知识存在但不知道走哪条面”

定义：

1. Curated plane
   - reviewed runtime pack
   - 面向 planning 显式任务
   - 高可信、显式 opt-in

2. Promoted plane
   - EvoMap active / candidate
   - 面向默认热路径
   - 强调复用与可检索

3. Evidence plane
   - KB hybrid
   - 面向宽召回、补证据、语义扩展
   - 不直接冒充高可信决策知识

验收：

- 每条 plane 有 source family allowlist
- 每条 plane 有 freshness / coverage / quality 指标
- 注入时可以解释 provenance

### Phase D：修 retrieval 合同，而不是只修入库

目标：

- 让真实用户 query 能撞上可用知识

动作：

1. 给高价值 atom 补 canonical / alt question
2. 增加 decision-oriented phrasing，不再只是报告切片
3. 保持 `USER_HOT_PATH` 保守，但新增：
   - planning explicit retrieval surface
   - diagnostic surface 的受控 `staged_fallback`
4. `staged_fallback` 必须受控：
   - planning only
   - bucket allowlist
   - `quality_auto >= 0.7`
   - 显式 provenance 标记

验收：

- 典型 planning query 不再在 EvoMap FTS 全空
- retrieval 结果能解释 active / candidate / staged_fallback 来源

### Phase E：把 KB hybrid 变成真正的 evidence plane

目标：

- 让向量能力变成可依赖能力，而不是偶发能力

动作：

1. 统一运行时环境，避免 `.venv` 有向量、`python3` 无向量
2. 分层扩充向量覆盖：
   - active + candidate atoms
   - reviewed planning docs
   - 高价值 staging slice
3. 补齐 KB provenance：
   - source_path
   - project
   - domain tags
   - structural_role
4. 对 vec-only hit 加审查与 explainability

验收：

- `kb_vectors` 覆盖明显增长
- live probe 稳定出现 vec-enabled hits
- vec hit 不再主要是泛 research/resource 噪音

### Phase F：接通反馈回路

目标：

- 让系统知道“什么知识真正帮助了回答”

动作：

1. 在回答后记录：
   - query
   - retrieved atom/doc ids
   - used_in_answer
   - user follow-up / correction / acceptance
2. 让 scorer / demotion / quarantine 能消费这些信号
3. 把 repeated correction 作为降级输入，而不是只做日志

验收：

- `answer_feedback` 不再是 0
- 能观察被多次纠正的 atom family
- candidate / active 的升降级开始有反馈依据

## 6. 优先级

### P0

1. Phase A 止血
2. Phase B family-aware groundedness + metadata 回填
3. Phase C 冻结 plane 合同

### P1

1. Phase D retrieval 合同修复
2. Phase E KB hybrid 稳定化

### P2

1. Phase F 反馈回路
2. 再评估是否需要更深的系统统一

## 7. 最终冻结判断

我对这轮问题的最终判断是：

> 现在最关键的不是“向量库数量太少”本身，而是知识对象、promotion 语义、retrieval 合同和反馈闭环都没有被治理成一个统一操作面。

因此正确路径不是：

- 先做全量向量化
- 先做系统大合并

而是：

- 先止血
- 再疏通 promotion
- 再冻结三条 plane 的职责
- 再修 retrieval 与 feedback

只有这样，后面的向量化和系统统一才不会把脏知识、弱知识和错知识放大。
