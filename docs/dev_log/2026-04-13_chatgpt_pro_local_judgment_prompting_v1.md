# 2026-04-13 ChatGPT Pro Local Judgment Prompting v1

## 背景

在 `chatgptrest-call` wrapper 已修复 maintenance env 自动加载之后，重新验证 `ChatGPT Pro`（`provider=chatgpt`, `preset=pro_extended`）用于内部技术判断时，出现了一类新的失败形态：

- conversation export 已落盘
- export 中确认模型确实是 `gpt-5-4-pro`
- 但 export 只有 `commentary` preamble 和一串 web/tool 搜索步骤
- 没有最终 answer text
- worker 在 `wait` 阶段反复 `conversation_exported -> wait_requeued -> browser_retry_scheduled`
- 最终命中 `WebRetryBudgetExceeded`

典型 job：

- `40a33a791cc249d48868f3e2e670d347`

## 结论

这不是 `Deep Research` 误路由，也不是 wrapper 把 `web_search=true` 偷偷打开了。

本次失败更接近 **问法 / 执行路径问题**：

- 用户要的是 `ChatGPT Pro` 的内部技术判断
- 但 prompt 是一个裸问题，且没有附本地审计上下文
- `pro_extended` 在 web UI 中自行发起 visible search/tool steps
- 在给出最终正文前耗尽了浏览器侧 retry budget

## 正确姿势

对 `ChatGPT Pro` 的内部技术判断 / 架构评审类问题：

1. 先写一个紧凑的本地 context memo
   - 只放当前 repo/runtime 已核实的事实
   - 不要让模型自己去补背景
2. 通过 `--file-path` 附带这个 memo
3. 在 question 里明确写：
   - `不要使用网页搜索`
   - `不要切到 deep research`
   - `只基于附件和常识判断`
4. 输出要求要窄
   - 先给 `yes/no`
   - 再给 `30/60/90 天路径`
   - 不要让它自由发散

## 推荐命令模板

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --no-agent \
  --maintenance-legacy-jobs \
  --provider chatgpt \
  --preset pro_extended \
  --idempotency-key pro-local-judgment-001 \
  --file-path /tmp/local_context.md \
  --question "你是 ChatGPT Pro，不要使用网页搜索，不要切到 deep research。只基于附件和常识做技术判断：先给 yes/no，再给可执行路径。" \
  --out-answer /tmp/pro-local-judgment-answer.md \
  --out-summary /tmp/pro-local-judgment-summary.json
```

## 对 shared skill 的影响

`skills-src/chatgptrest-call/SKILL.md` 已同步加入这条硬规则，避免多 agent 继续把 repo/runtime 内部判断题问成“先上网搜索再总结”。
