# KB + Planning High-Quality Harness Execution TODO Master V5

## 已完成

- [x] live bulk groundedness scoring
- [x] live `staged -> candidate`
- [x] live `candidate/staged -> active`
- [x] live `chain_id` backfill
- [x] chain live apply 改为 metadata-only 安全模式
- [x] before/after DB 聚合验收

## 本轮确认完成的数字

- [x] `active = 816`
- [x] `candidate = 4312`
- [x] `groundedness_audit = 3445`
- [x] `chain_nonempty = 103259`

## 残余项

- [ ] 对扩容后的 `active+candidate` 做 EvoMap 向量重建
- [ ] 为“绿源 / 钛虎 / 来访准备”建立 semantic bridging / query normalization
- [ ] 让 retrieval 显式利用 `chain_rank / is_chain_head`
