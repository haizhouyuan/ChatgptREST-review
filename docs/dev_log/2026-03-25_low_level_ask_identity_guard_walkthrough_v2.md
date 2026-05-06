# 2026-03-25 Low-Level Ask Identity Guard Walkthrough v2

## 这版修什么

v1 的主方向没错，但客户端复测指出了两个 production-safety 缺口：

1. test-only exemption 可被 `User-Agent: testclient` 伪造
2. `allow_with_limits` 只是“看起来很完整”的 contract，入口其实没按它执行

这次 v2 做的是 hardening，不是推翻 v1。

## testclient exemption 为什么危险

v1 里 low-level ask 的 identity 豁免，本意只是让本仓库的 FastAPI `TestClient` 单测不必为每个 case 都补注册身份。

但如果判断条件只有：

- `user-agent` 里包含 `testclient`

那真实请求只要伪造这个 header，也会被当成测试流量。

v2 的修法是把豁免收窄到“真实的 in-process TestClient 形态”：

- `user-agent` 里有 `testclient`
- `request.client.host == "testclient"`
- 仍然没有任何显式 client identity

这样：

- 仓库单测继续方便
- 网络请求无法只靠 header 伪造豁免

## allow_with_limits 为什么不能只审计

如果 classifier 输出：

- `allow_with_limits`
- `allow_pro=false`
- `allow_deep_research=false`
- `min_chars_override=0`

但入口只是把这段 JSON 塞进 `params.ask_guard`，却不去改真实 `params`，那效果还是：

- 要么完全放行
- 要么完全阻断

这会让 contract 看起来比真实行为更强，长期会误导客户端和维护者。

v2 把这块补成了真实 enforcement：

- downgrade `preset`
- 关闭 `deep_research`
- 写回 `min_chars`
- 并把实际生效结果记到 `ask_guard.enforced_limits`

如果某个 provider 根本没有 non-Pro low-level preset，而 classifier 又要求“allow but no Pro”，就 fail-closed，不伪装成已经受控。

## 结果

v2 之后，这条链路变得更一致：

- test-only exemption 只属于真实测试
- gray-zone allow 不再是假象
- README / contract / runbook 的示例和行为重新对齐

也就是说，low-level ask 现在不是“先做了一版规则，文档看起来很严”，而是：

- 入口真的能识别来源
- 真的能阻断冒充
- 真的能把 classifier 的限制落实到请求参数
