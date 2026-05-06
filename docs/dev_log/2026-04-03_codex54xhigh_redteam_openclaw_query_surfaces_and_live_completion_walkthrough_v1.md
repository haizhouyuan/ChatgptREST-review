# 2026-04-03 Codex 5.4-xhigh Redteam OpenClaw Query Surfaces And Live Completion Walkthrough v1

## 这轮怎么用红队

1. 先让 `codex 5.4-xhigh` 审未提交批次
2. 我只采纳它指出的事实性 bug 和边界缺口
3. 修完后再让它复审
4. 不把红队意见当最终真理，而是和代码、测试、live 证据一起交叉核验

## 最终结果

1. 第一轮红队是 `reject`
2. 我修完后第二轮收敛到 `approve-with-fixes`

## 剩余口径

剩下的问题已经不是“这批不能交”，而是：

1. 下一批要不要继续收 session REST boundary
2. read-time refresh 未来要不要迁到专门 refresh path
