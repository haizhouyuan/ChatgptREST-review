## 1. Verdict

**不允许当前 controller 最终以 `HARD_EXTERNAL_BLOCKER` 收口。**

当前包可以保持 **`production-usable: blocked`**，也可以说 **“存在 hard-external key-rotation blocker”**，但不能把整个终局判断压缩成 **`HARD_EXTERNAL_BLOCKER`**。原因是：按你给的终局规则，只有在“所有本地可执行工作都已完成”后，剩余 provider/account/user 授权才可以终局为 `HARD_EXTERNAL_BLOCKER`。当前证据包仍有本地可执行的 P0/P1，尤其是 evidence package/manifest 自洽、secret closeout、dashboard/governance finalization、Finbot future-run guard 语义等问题。

我的 hard review 结论是：

> **当前状态：`BLOCKED_LOCAL_P0_BEFORE_HARD_EXTERNAL_BLOCKER`**
> **不是：`HARD_EXTERNAL_BLOCKER`**
> **更不是：`PASSED` / `production-ready`**

---

## 2. P0 / P1 / P2 Findings

### P0-1 — Evidence manifest / verifier 不足以支撑 terminal hard review

`docs/paperclip_evidence_manifest_full_20260507.json` 声称有 **33 个 artifacts**，`docs/manifest_verifier_result_20260507.json` 声称 `status: pass`、`artifact_count: 33`、`errors: []`。但是我解包后按 manifest hash 对照，当前附件包只能直接校验到 **20/33**，有 **13 个 manifest artifacts 缺失**。这不是外部 blocker，是本地 evidence packaging / verifier scope 问题。

缺失项如下：

| Manifest artifact id       |      Issue | 缺失路径                                                                           |
| -------------------------- | ---------: | ------------------------------------------------------------------------------ |
| `MASTER-PLAN`              |          — | `docs/superpowers/plans/2026-05-07-paperclip-unblock-to-passed-master-plan.md` |
| `PAP12-FRESH-SMOKE`        |   `PAP-12` | runtime fresh smoke JSON                                                       |
| `PAP12-FRESH-SMOKE-MATRIX` |   `PAP-12` | runtime smoke matrix MD                                                        |
| `PAP13-EVIDENCE-MANIFEST`  |   `PAP-13` | `PAP13_OptionE_evidence_manifest.json`                                         |
| `PAP13-VALIDATOR`          |   `PAP-13` | `PAP13_OptionE_validator_result.json`                                          |
| `PAP21-CONFIG-GATE`        |   `PAP-21` | `PAP21_config_gate_v2_record_20260507.json`                                    |
| `PAP21-MEMORY-CLOSEOUT`    |   `PAP-21` | `PAP21_memory_closeout_20260507.json`                                          |
| `PAP22-KIMI-TIMEOUT-FIX`   |   `PAP-22` | `kimicode_mcp_timeout_fix_20260507.json`                                       |
| `PAPA21-NON-CLAIM`         |  `PAPA-21` | `docs/governance_ar_p0_001_non_claim_enforcement_closeout_20260507.md`         |
| `PAPA22-ACTION-REGISTER`   |  `PAPA-22` | `docs/paperclip_pro_review_action_register_20260507.md`                        |
| `PAPAA15-H8-READBACK`      | `PAPAA-15` | `H8_paperclip_readback_20260507.json`                                          |
| `FIN13-FINAL-GATE`         |   `FIN-13` | `FIN-COMPANY-013_final_gate_report.md`                                         |
| `FIN13-MEMORY-GATE`        |   `FIN-13` | `memory_integration_gate.md`                                                   |

这会直接破坏“full evidence manifest verifier 足够”的判断。当前 verifier 结果最多说明它可能在 controller 的原始文件系统上跑过，但它没有证明 **最终交付证据包** 是自包含、可复核、hash-complete 的。对于 terminal closeout，这不够。

**Severity: P0.**
**本地必须修。**

---

### P0-2 — PAPA-21 / PAPA-22 仍是本地 governance blockers，不能被 HARD_EXTERNAL_BLOCKER 吞掉

Dashboard 和 blocker board 都显示：

* `PAPA-21` = `blocked`
* `PAPA-22` = `blocked`
* `P0-GOVERNANCE-FINAL-LOCK` = `blocked`
* `P0-PRO-P0-ACTION-HANDLING` = `blocked`

这些不是 provider/account/user 授权 blocker，而是本地 governance/action-register blocker。它们可以在“等待 hard review”期间保持 blocked；但在 controller 准备给用户最终回复时，不能仍以本地 blocked 状态存在。

特别是现在这次 hard review 返回了新的 P0/P1，本地 controller 必须把它们写入 `PAPA-22` action register，并据此保持 blocked 或修完后重新 close。不能说“PAPA-21/PAPA-22 blocked，但整体 terminal 是 HARD_EXTERNAL_BLOCKER”。这违反 hard-external 的定义。

**Severity: P0.**
**本地必须修。**

---

### P0-3 — MCP/skill secret closeout 不完整；当前不能只列 MiniMax/DeepSeek

MCP closeout 的方向是对的：active config 中移除了 MiniMax 和 DeepSeek inline key，并且 provider-side rotation 被列为外部 blocker。但是 hard review 下还有三个严重缺口：

第一，文档的 historical exposure 表列出了 **MiniMax、DeepSeek、Tavily、Brave** 四类 key exposure，但 hard external blockers 只列 MiniMax 和 DeepSeek。Tavily/Brave 要么已经完成 provider-side rotation 并给出证据，要么也必须进入 external rotation blocker。现在没有这个证明。

第二，closeout 提到创建了这些 backup：

* `~/.claude.json.bak.papa23-minimax-key-remove`
* `~/.deepseek/config.toml.bak.papa23-deepseek-key-remove`

这些 backup 是在移除 key 前后创建的。当前证据没有证明它们不含 raw secret、已加密、已销毁、或至少权限 fail-closed。active config clean 不等于 secret closeout clean；secret-bearing backup 仍是本地可执行风险。

第三，MiniMax/Tavily/Brave 等 key-backed MCP 仍被 lifecycle board 标为 `LIVE`。如果 key values retain historical exposure risk，而 rotation 还没完成，本地 controller 至少可以 fail-close：禁用受影响 MCP，或明确标记“blocked pending rotation, no production use”。把受历史暴露影响的 provider 继续标为 live，不是 fail-closed posture。

**Severity: P0.**
**本地必须修。Provider-side rotation 是外部，但 backup cleanup / local disable / blocker enumeration 是本地。**

---

### P0-4 — Operator dashboard 是“部分 fail-closed”，但不能作为最终 fail-closed dashboard

Dashboard 有优点：`productionReady: false`，没有 claim `PASSED`，并明确列出 blocker。这部分是 fail-closed。

但当前 dashboard 不可作为最终 terminal dashboard，原因：

* `terminal_label` 是 `HARD_EXTERNAL_BLOCKER_PENDING_PRO_REVIEW`，不是 final label。
* `pro_review_ready_after_packaging: true` 与当前包缺 13 个 manifest artifacts 相冲突。
* `masterAcceptanceFailures` 里同时列出 hard external blocker、本地 governance P0、本地/未来 Finbot P1。只要这里还有非 external 的 P0/P1，就不能让 controller 最终回复 `HARD_EXTERNAL_BLOCKER`。
* `operator_dashboard_validator_result_20260507.json` 只有 `{ "status": "pass", "errors": [] }`，没有证明 validator 检查了“不存在本地 P0/P1”、“所有 external blockers 枚举完整”、“dashboard 与 manifest/readback 一致”等核心规则。

**Severity: P0.**
**本地必须修。**

---

### P1-1 — Finbot research-only closeout 可以保留，但 kill-switch 只是当前停止，不是 durable launcher guard

Finbot closeout 没有 claim advice/watchlist/trading/signal，这一点是对的。`Finbot Orchestrator` 被 pause，也是必要的 fail-closed 止血。

但注意：FIN-15 自己记录了 agent 已经违反 instruction-only boundary，并且未来需要 launcher-level denylist。当前只有 pause 单个 agent ID：

`ff8b06ea-7069-4fb7-ab2d-aecf87c48c92`

这对于“现在不再跑 Finbot agent”是够的；对于“未来任何 Finbot agent/company run 都不会绕过 boundary”不够。当前可以把它作为 **blocked terminal 的安全边界**，但不能把它当成 production-grade Finbot guard。

因此：

* 若 final scope 是 **research-only, no further Finbot runs**：当前 pause 可以接受，但必须在 dashboard/action register 中写清楚“任何 resume 前必须先过 launcher denylist gate”。
* 若 final scope 允许未来 Finbot company agent 自动执行：不允许，必须先实现 launcher denylist。

**Severity: P1 for terminal-blocked closeout；P0 if any future Finbot autonomous run is allowed before denylist.**

---

### P1-2 — MCP/skill lifecycle board 有 active-but-untested 项，不能 claim full production optimization pass

MCP closeout 中：

* `figma` 是 Tier-2，但 `NOT TESTED`
* `markdown-to-pdf` 是 active skill，但 `Pending formal test`
* Validator summary 却说 lifecycle completeness / skill usability pass

这不是 secret blocker，但它影响 “MCP/skill production optimization closeout” 的精确性。Fail-closed 做法应该是：

* 未测试 active 项降级为 `candidate` / `research_only` / `blocked`
* 或补 formal smoke / usability test
* 或明确声明“不参与 production acceptance”

**Severity: P1.**

---

### P1-3 — H8 memory governance policy 本身 fail-closed，但 readback/sync 证据不完整

H8 决策内容是正确方向：

* 外部 provider authority promotion = 0
* Paperclip-native EvidenceLog / AuthorityLedger 保留
* Graphiti quarantined
* Supermemory blocked
* MemPalace challenger-only
* GBrain sandbox-only

这满足“Local/external memory provider 不得提升 authority”的安全目标。

但 H8 文档自身仍写着：

* `Paperclip sync to PAPA-24 | PENDING`
* `PAPAA-15 superseded by this decision | To be actioned by Controller`

Dashboard/manifest 又声称 `PAPA-24` 和 `PAPAA-15` done。缺失的 `H8_paperclip_readback_20260507.json` 正好是关键 readback。当前包里没有这个 artifact，所以证据链不完整。

**Severity: P1，若作为 terminal evidence 则升为 P0 packaging issue。**

---

### P1-4 — FIN-13 语义要修正：要么是未来 scope blocker，要么是当前 master P1 blocker，不能两者兼有

Blocker board 说：

`FIN-13` blocked，但 “not required for research-only master scope”。

Dashboard 又把 `P1-FINBOT-MATERIAL-CONNECTOR-VALIDATOR-MEMORY` 放在 `masterAcceptanceFailures` 里。

这两个语义冲突。若 FIN-13 不属于本轮 research-only terminal scope，就不要放在 master acceptance failures；应放到 future full-Finbot blocker。若它属于 master acceptance failures，则当前仍有本地 P1，不允许 HARD_EXTERNAL_BLOCKER。

**Severity: P1；影响 final label 时为 P0。**

---

### P2 findings

这些不单独阻止 blocked terminal，但建议修：

* Manifest schema 建议显式加入 `terminal_issues`，不要只让 verifier result 派生。
* Verifier result 应输出 `checked_artifacts[]`，包含 `id/path/expected_sha256/actual_sha256/exists/result`，而不是只有 summary。
* Final review packet 应有 packet-level SHA-256 和 zip file manifest。
* `PLA-22` validator 文本里有一个 key 写成 `" Pla-14_cancelled"`，前导空格不影响主结论，但应清理。
* Dashboard validator 应输出规则列表，例如 `productionReady_false`, `no_passed_claim`, `no_local_p0_p1_unresolved`, `all_external_blockers_enumerated`, `manifest_hash_complete`, `forbidden_claim_scan_pass`。

---

## 3. 哪些必须立即本地修

### 必修 A — 重新打包 self-contained evidence packet，并在最终 zip 解包目录上 rerun verifier

当前最直接的本地 P0 是：**证据包不能独立复核 manifest**。

必须补齐上面列出的 13 个 missing artifacts，或者修改 manifest 明确说明这些 artifacts 不属于 final packet 并提供可接受的替代证据。但如果 manifest 继续声称 33 个 artifact，final packet 就必须包含 33 个 artifact，且 hash 全部匹配。

最低要求：

1. `docs/paperclip_evidence_manifest_full_20260507.json` 中每个 artifact 都能在 final packet 内找到。
2. `sha256` 全部匹配。
3. `docs/manifest_verifier_result_20260507.json` 必须是在 **final packet 解包目录** 上跑出来的，不是在 controller 原始文件系统上跑出来的。
4. verifier result 必须列出每个 artifact 的 path-level check，不只是 `status: pass`。

---

### 必修 B — 修 PAPA-21 / PAPA-22

`PAPA-21` 和 `PAPA-22` 当前仍是本地 governance blockers。收到这次 review 后，controller 必须：

* 更新 `docs/paperclip_pro_review_action_register_20260507.md`
* 把本 review 的 P0/P1 逐项登记
* 对每项给出 `fixed / external / future_scope / blocked` 的状态
* 重新生成 dashboard、blocker board、current truth、manifest
* 重新 close 或保持 blocked

如果本 review 的 P0 未修，`PAPA-22` 必须继续 blocked，controller 不能 terminal。

---

### 必修 C — 修 secret closeout

必须立即完成或证明以下事项：

1. 对 `~/.claude.json.bak.papa23-minimax-key-remove`、`~/.deepseek/config.toml.bak.papa23-deepseek-key-remove` 以及任何 Kimi/Tavily/Brave 相关 backup 做 secret scan。
2. 若 backup 含 raw secret：删除、加密、或移入权限受控 vault，并给出 proof。
3. Tavily/Brave historical exposure：

   * 要么补 provider-side rotation 证据；
   * 要么加入 hard external rotation blocker；
   * 要么证明之前已经 rotate/revoke。
4. MiniMax/DeepSeek/Tavily/Brave 若仍 pending rotation，不应在 dashboard 中作为 production-live dependency；要么禁用对应 MCP，要么标记 blocked/no production use pending rotation。
5. `credentials.env` 的权限和 ownership 要有证据，例如 `600` 或更严格；不能只说 “file-system restricted”。

---

### 必修 D — 修 operator dashboard final semantics

最终 dashboard 必须满足：

* `productionReady: false`
* 不出现 `PASSED` / `production-ready`
* `terminal_label` 只能在所有本地 P0/P1 修完后才变成 `HARD_EXTERNAL_BLOCKER`
* `masterAcceptanceFailures` 中不能保留本地可执行 P0/P1
* `hard_external_blockers` 必须枚举所有仍需用户/provider/account 授权的 blockers
* `blocked_governance` 在 final hard-external 回复前应为空，或明确是“已被本 review P0 阻塞”，此时就不能 final hard-external

---

### 必修 E — Finbot future-run guard 语义固定

至少要做其一：

* **方案 1：不实现 denylist，但严格 terminal no-run**
  Dashboard/action register 写清：Finbot Orchestrator remains paused；任何 resume 或新 Finbot agent run 在 launcher-level denylist gate 通过前禁止。此时 FIN-15 是 research-only closeout，FIN-13/Finbot full build 是 future scope，不属于当前 masterAcceptanceFailures。

* **方案 2：实现 launcher denylist**
  添加 policy + validator artifact，禁止 `TradingAgents`、`tradingagents_adapter`、`run_tradingagents`、`finbot_orchestrator.py`、ticker/date default runs、`pip install`、broker/order/trading API commands。然后 FIN-15 的 future guard 可以关闭。

当前证据只做到 pause，不能允许任何 further Finbot autonomous run。

---

## 4. 哪些是真正 hard external blocker

当前可以接受为 hard external 的只有 provider/account/user 授权类事项，但前提是本地防护已完成。

### 可以是 hard external blocker

| Blocker                                    | 条件                                                                              |
| ------------------------------------------ | ------------------------------------------------------------------------------- |
| MiniMax provider-side key revoke/rotation  | active config/backups 已清理；MiniMax MCP pending rotation 时禁用或标记 no-production-use |
| DeepSeek provider-side key revoke/rotation | active config/backups 已清理；DeepSeek key 不再存在 plaintext backup                    |
| Tavily provider-side key rotation          | 如果 historical exposure 未证明已 rotate，则必须加入                                        |
| Brave provider-side key rotation           | 如果 historical exposure 未证明已 rotate，则必须加入                                        |

### 不应作为当前 terminal hard external blocker

| 项                                                                     | 原因                                                                                                                                                                         |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PAPA-21/PAPA-22                                                       | 本地 governance/action-register blocker，不是外部授权                                                                                                                               |
| FIN-13 material/connector/validator/memory blockers                   | 若是 future full-Finbot build，则不是当前 terminal blocker；若是当前 master scope，则是本地 P1                                                                                               |
| Finbot launcher denylist                                              | 本地可执行 guard，不是外部授权                                                                                                                                                         |
| Manifest/evidence packaging                                           | 本地可执行                                                                                                                                                                      |
| Secret-bearing backups cleanup                                        | 本地可执行                                                                                                                                                                      |
| Figma / markdown-to-pdf untested active status                        | 本地可执行：test 或 demote                                                                                                                                                        |
| Graphiti `OPENAI_API_KEY` / Supermemory DPA / provider promotion gaps | 当前 memory authority 已 fail-closed，Paperclip-native baseline retained；这些是 future provider promotion blockers，不应阻塞当前 blocked terminal unless scope claims provider promotion |

---

## 5. 是否允许 controller 最终以 `HARD_EXTERNAL_BLOCKER` 回复用户

**当前不允许。**

允许条件是：

1. 当前发现的本地 P0 全部修完；
2. 当前发现的 P1 要么修完，要么明确降为 future scope 且从 `masterAcceptanceFailures` 移除；
3. PAPA-21/PAPA-22 消化本次 review 后重新 close 或保持 blocked；如果保持 blocked，就不能 final hard-external；
4. Final dashboard 不再显示任何本地 unresolved P0/P1；
5. Hard external blocker list 完整覆盖所有未 rotate 的 historically exposed keys；
6. Final evidence packet 可独立复核 manifest hash。

满足后，controller 可以回复：

> `production-usable: blocked; terminal blocker: HARD_EXTERNAL_BLOCKER — provider/account key rotation required; no production-ready claim.`

不能回复：

> `PASSED`
> `production-ready`
> `all blockers are external`
> `Finbot production-ready`
> `MCP/skills fully production-optimized`，除非 active-but-untested 项已 test/demote 且 secret closeout 完整。

---

## 6. Exact artifact / issue / command requirements

### 6.1 必须补入 final packet 的 artifact

至少补入这些 manifest-listed artifacts，或从 manifest 删除并给出替代证据：

```text
docs/superpowers/plans/2026-05-07-paperclip-unblock-to-passed-master-plan.md

evidence/runtime/runtime_task_smoke_results_fresh_20260507.json
evidence/runtime/runtime_task_smoke_matrix_fresh_20260507.md
evidence/runtime/PAP13_OptionE_evidence_manifest.json
evidence/runtime/PAP13_OptionE_validator_result.json
evidence/runtime/PAP21_config_gate_v2_record_20260507.json
evidence/runtime/PAP21_memory_closeout_20260507.json
evidence/runtime/kimicode_mcp_timeout_fix_20260507.json

docs/governance_ar_p0_001_non_claim_enforcement_closeout_20260507.md
docs/paperclip_pro_review_action_register_20260507.md
docs/memory_agent_system_20260507/H8_paperclip_readback_20260507.json

paperclip_finbot/company_runs/2026-05-07_finbot_complete_company_execution/FIN-COMPANY-013_risk_qa_memory_gate/FIN-COMPANY-013_final_gate_report.md
paperclip_finbot/company_runs/2026-05-07_finbot_complete_company_execution/FIN-COMPANY-013_risk_qa_memory_gate/memory_integration_gate.md
```

如果 runtime evidence 保留在 absolute Paperclip instance path，也要在 zip 内保留一个可映射路径，并在 manifest 中声明 mapping。

---

### 6.2 必须更新/修复的 issue

```text
PAPA-21  Governance final non-claim enforcement
PAPA-22  Pro P0 action register / hard review action handling
PAPA-23  MCP/skill secret closeout revision
PAPAA-15 H8 readback / supersession proof
FIN-15   Research-only closeout + future-run denylist/no-resume guard
FIN-13   Reclassify as future full-Finbot blocker or current P1
LOC-4    No new work required except including full snapshots/logs in packet
```

如不想 reopen `PAPA-23`，可以创建新的 child issue，但 final dashboard 必须能追溯到它。

---

### 6.3 必须生成/更新的 artifact

```text
docs/manifest_verifier_result_20260507.json
docs/operator_dashboard_validator_result_20260507.json
docs/paperclip_operator_dashboard_20260507.md
docs/paperclip_operator_dashboard_20260507.json
docs/paperclip_company_blocker_board_20260507.md
docs/paperclip_company_execution_matrix_20260507.md
docs/paperclip_production_current_truth_20260507.md

docs/mcp_skill_secret_full_closeout_20260507.json
docs/mcp_skill_secret_full_scan_20260507.json
docs/mcp_skill_key_rotation_blocker_register_20260507.md

docs/finbot_research_only_agent_killswitch_20260507/no_resume_until_denylist_gate_20260507.md
# or, if implemented:
docs/finbot_research_only_agent_killswitch_20260507/launcher_denylist_policy_20260507.json
docs/finbot_research_only_agent_killswitch_20260507/launcher_denylist_validator_20260507.json

docs/review_packet_sha256_manifest_20260507.txt
```

---

### 6.4 必须跑的 final packet manifest check

不要只在原始 repo 上跑；必须在 **final zip 解包目录** 上跑。最低命令要求如下：

```bash
unzip -q paperclip_production_unblock_hard_review_packet_FINAL_20260507.zip -d /tmp/paperclip_final_packet
cd /tmp/paperclip_final_packet

python3 - <<'PY' > docs/review_packet_manifest_recheck_20260507.json
import json, os, hashlib

manifest_path = "docs/paperclip_evidence_manifest_full_20260507.json"
m = json.load(open(manifest_path, "r", encoding="utf-8"))

def candidates(path):
    out = []
    out.append(path.lstrip("/"))
    prefixes = [
        "/vol1/1000/projects/toyresearch/",
        "/REDACTED_HOME/.paperclip/instances/default/projects/91916737-9533-4d63-9c1e-e04894dabd41/8506d363-3d0a-44f4-b6f6-5bf262d373f1/_default/",
    ]
    for p in prefixes:
        if path.startswith(p):
            out.append(path[len(p):])
    return list(dict.fromkeys(out))

checked, missing, bad_hash = [], [], []

for a in m["artifacts"]:
    found = None
    for c in candidates(a["path"]):
        if os.path.exists(c):
            found = c
            break

    if not found:
        missing.append({"id": a["id"], "issue": a.get("issue"), "path": a["path"]})
        continue

    actual = hashlib.sha256(open(found, "rb").read()).hexdigest()
    row = {
        "id": a["id"],
        "issue": a.get("issue"),
        "packet_path": found,
        "expected_sha256": a["sha256"],
        "actual_sha256": actual,
        "ok": actual == a["sha256"],
    }
    checked.append(row)
    if not row["ok"]:
        bad_hash.append(row)

result = {
    "status": "pass" if not missing and not bad_hash else "fail",
    "artifact_count_manifest": len(m["artifacts"]),
    "artifact_count_checked": len(checked),
    "missing": missing,
    "bad_hash": bad_hash,
    "checked_artifacts": checked,
}
print(json.dumps(result, indent=2, ensure_ascii=False))
PY

jq -e '.status == "pass" and (.missing|length == 0) and (.bad_hash|length == 0)' \
  docs/review_packet_manifest_recheck_20260507.json
```

`jq` 必须 pass。否则不允许 terminal。

---

### 6.5 必须跑的 secret closeout check

最低要求：

```bash
# 1) 扫 active configs + known backups + project evidence，禁止 raw key 留在非 credentials.env 位置
python3 paperclip_company_os/validators.py secret-scan \
  --redact \
  --paths "$HOME/.kimi" \
  --paths "$HOME/.cursor" \
  --paths "$HOME/.gemini" \
  --paths "$HOME/.codex" \
  --paths "$HOME/.codex2" \
  --paths "$HOME/.claude.json" \
  --paths "$HOME/.claude.json.bak.papa23-minimax-key-remove" \
  --paths "$HOME/.deepseek" \
  --paths "$HOME/.deepseek/config.toml.bak.papa23-deepseek-key-remove" \
  --paths "/vol1/1000/projects/toyresearch/docs" \
  --paths "/vol1/1000/projects/toyresearch/paperclip_finbot" \
  --allow-secret-file "/vol1/maint/MAIN/secrets/credentials.env" \
  --output docs/mcp_skill_secret_full_scan_20260507.json

# 2) credentials.env 权限 proof
stat -c '%a %U:%G %n' /vol1/maint/MAIN/secrets/credentials.env \
  > docs/credentials_env_permissions_20260507.txt
```

如果 `secret-scan` CLI 不存在，必须用等价工具实现同等检查；最终 artifact 必须包含：

```text
docs/mcp_skill_secret_full_scan_20260507.json
docs/credentials_env_permissions_20260507.txt
docs/mcp_skill_key_rotation_blocker_register_20260507.md
```

其中 blocker register 必须明确 MiniMax、DeepSeek，以及 Tavily/Brave 是否已 rotate；未 rotate 就列入 hard external blocker。

---

### 6.6 必须跑的 dashboard final validator

最终 dashboard validator 不能只输出 `status/pass`。它必须至少验证这些规则：

```text
productionReady == false
no "PASSED" / "production-ready" claim
no unresolved local P0 in masterAcceptanceFailures
no unresolved local P1 in masterAcceptanceFailures unless explicitly future_scope
hard_external_blockers covers all unrotated historically exposed keys
PAPA-21/PAPA-22 not left blocked if final terminal_label == HARD_EXTERNAL_BLOCKER
manifest verifier status == pass on final packet
Finbot forbidden claims absent
Local LLM route quarantine status == pass
Memory provider authority promotions == 0
```

建议输出：

```json
{
  "status": "pass",
  "rules": {
    "productionReady_false": "pass",
    "no_passed_claim": "pass",
    "no_unresolved_local_p0": "pass",
    "no_unresolved_local_p1_in_terminal_scope": "pass",
    "all_external_key_blockers_enumerated": "pass",
    "papa21_papa22_finalized": "pass",
    "manifest_packet_hash_complete": "pass",
    "finbot_forbidden_claim_scan": "pass",
    "local_llm_quarantine": "pass",
    "memory_authority_zero_promotion": "pass"
  },
  "errors": []
}
```

---

## Bottom line

当前包的安全方向是对的：没有 claim production-ready，Finbot 被降为 research-only，Local LLM 被禁用，memory providers fail-closed，MCP inline secrets 已从 active configs 移除。

但 hard review 下，**证据包不完整、secret closeout 有本地残留风险、PAPA-21/PAPA-22 仍是本地 blocked、dashboard final semantics 不成立**。所以 controller 还不能停。

**最终判断：不允许现在以 `HARD_EXTERNAL_BLOCKER` 回复用户。必须先修上述本地 P0；修完后若只剩 provider-side key rotation，才允许以 `HARD_EXTERNAL_BLOCKER` 终局。**
