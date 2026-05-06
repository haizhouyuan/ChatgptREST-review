# KB + Planning High-Quality Harness Residual Risk Note V2

## 1. 业务 query 召回仍有明显短板

promotion 和 chain 已经 live 落地，但以下 query 仍可能得到 `0 hit` 或弱命中：

- 绿源来访准备
- 钛虎机器人关节模组合作来访

已核到的原料稀缺度：
- `绿源`: `4`
- `钛虎`: `0`
- `来访`: `6`

这说明当前剩余问题不是 promotion 是否跑通，而是：
- 原始语料里公司名/事件名本来就稀缺
- atom 形态和真实 query 形态仍不一致

## 2. 向量扩容仍是长算子

EvoMap vector lane 本身已可用，但 promotion 扩容后，要把 `active+candidate` 全量重编码进 [evomap_vectors.db](/vol1/1000/projects/ChatgptREST/data/evomap_vectors.db) 仍是高耗时长算子。

本轮没有把这件事继续当成 release blocker。

## 3. chain 语义已安全，但 supersession 语义仍未接管 retrieval

本轮 live chain apply 采用的是 metadata-only 模式：
- 回填 `chain_id / chain_rank / is_chain_head / superseded_by`
- 不重写 `promotion_status`

这避免了破坏 live promotion，但也意味着：
- retrieval 还没有开始主动利用 `chain_rank / is_chain_head`
- “最新版本优先”还不是完整终局

## 4. 真实边界

本轮已经完成的是：
- promotion pipeline from fake-green to real-green

本轮没有声称完成的是：
- semantic recall endgame
- query normalization endgame
- full vector rebuild endgame
