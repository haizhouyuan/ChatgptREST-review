# 2026-03-09 Guardian Issue Close After Success

## 做了什么

把 issue ledger 的第二阶段自动收口补到了 guardian：

- `open/in_progress -> mitigated`
  - 继续沿用原有 TTL quiet-window 自动收口
- `mitigated -> closed`
  - 新增自动规则：
    - mitigated 之后
    - 同客户端 / 同 `kind`
    - 至少 `3` 次 qualifying success
    - 且无 recurrence
  - 满足后，guardian 自动更新 issue 为 `closed`

代码：

- `ops/openclaw_guardian_run.py`
- `tests/test_openclaw_guardian_issue_sweep.py`

配置：

- `CHATGPTREST_CLIENT_ISSUE_CLOSE_AFTER_SUCCESSES`
- `CHATGPTREST_CLIENT_ISSUE_CLOSE_MAX`

## 为什么这么做

之前的自动收口只做到：

- 长时间无复发 => `mitigated`

这只说明“当前看起来收住了”，还不能说明“真实客户端已经再次穿透使用过并且没再出问题”。

新规则的目标是把 `closed` 从维护者主观判断推进到更可计算的状态：

- `mitigated` = live 验证已通过
- `closed` = mitigated 后已有 3 次以上真实客户端成功使用且无复发

## 当前第一版的 qualifying success 口径

guardian 现在按以下条件计数：

- `jobs.kind == issue.kind`
- `jobs.status == completed`
- `jobs.created_at > mitigated_ts`
- job 的 client name 不是系统内建维护客户端
- job 的 client name 与 issue.project 一致

这是一个保守但可落地的第一版。

## live dry-run 结果

在当前库上做过一次 dry-run：

- 有 `16` 条 `mitigated` issue 满足自动 `closed` 条件
- 样本主要来自：
  - `chatgptrest_gemini_ask_submit`
  - `gemini_web.ask`

说明这条机制不是空转，且当前已有历史单可以被系统性收口。

## 风险与边界

这还不是最终的 family-aware close engine。

当前版本仍有这些边界：

- 只按 `project + kind` 做收口，不是完整 issue-family 图
- recurrence 只看同 issue 的再次 `issue_reported`
- 还没纳入更细粒度的 signal family / provider family / route family

所以这版的定位是：

- 先把 `closed` 从纯人工状态推进到“有真实客户端成功证据”的自动状态
- 后面再升级成 family-aware close rule
