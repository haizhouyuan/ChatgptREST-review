# Gemini Zip 上传失败根因报告 (v2)

**Job**: `0d44c139965c4d5a848b8a7f790aa230`  
**日期**: 2026-03-17（v2 修订基于 Codex 评审反馈）  

## 结论

**Drive 上传成功，真正的缺陷在 Gemini send/follow-up 语义。** 执行器把 base `/app` URL 错误地当成可恢复对话上下文，在 `send_without_new_response_start` 时触发 `GeminiFollowupSendUnconfirmed`，导致既没有稳定 thread URL，也拒绝继续 wait。附件未插入是强假设，但独立于 follow-up guard 的代码缺陷。

## 已证实根因（代码层面）

### 根因 1: follow-up guard 对 `/app` 的误判

`gemini_web_mcp.py` L2487 和 L2498:
```python
# 修复前（错误）:
if status == "in_progress" and initial_conversation_url and send_without_new_response_start:
    # ↑ initial_conversation_url 只检查 truthiness，bare /app 也通过

# 修复后（正确）:
if status == "in_progress" and initial_conversation_url and _is_gemini_thread_url(initial_conversation_url) and send_without_new_response_start:
    # ↑ 必须是真正的 thread URL (/app/{hash}) 才触发 guard
```

**证据**:
- `run_meta.json` 明确记录 `conversation_url: "https://gemini.google.com/app"` — 这是 base URL，不是 thread URL
- `followup_wait_guard.activated: true` 且 `input_conversation_url: "https://gemini.google.com/app"` — bare URL 触发了 guard
- 深度思考 fallback 代码 (L2397-2403) **已经正确检查** `_is_gemini_thread_url()`，但主 guard 路径遗漏了

### 根因 2: zip 展开策略仅限 deep_research

`gemini_web_mcp.py` `_prepare_gemini_file_paths_for_upload()`:
- 现有 zip 展开功能 **已存在** （via `_extract_zip_for_gemini`），但只在 `deep_research=True` 时执行
- 此 job `deep_research_effective=false`，`zip_expanded_count=0`
- **注意**: 这不是"新增 zip 预解压能力"，而是"把现有 zip 展开策略扩到普通 ask"

### 不是根因（澄清）

| 假设 | 状态 | 说明 |
|------|------|------|
| Drive 上传失败 | ❌ 已排除 | `upload_completed: true`, `rclone` 校验通过 |
| Send 超时不够 | ❌ 非主修复 | 失败是 guard 主动拦截 (`GeminiFollowupSendUnconfirmed`)，不是超时 |
| 附件未插入 | ⚠️ 未证实 | 用户看到 thread 无附件，但 driver 日志不够细 |

## 证据链

### 1. Drive 上传 ✅
```
drive_id: 1EEYmtl5UKJpCU9FRA6klFt8eJFkm_bsh
drive_url: https://drive.google.com/open?id=1EEYmtl5UKJpCU9FRA6klFt8eJFkm_bsh
upload_completed: True
size_bytes: 110103
```

### 2. Driver Send → Guard 拦截 ❌
```
conversation_url: https://gemini.google.com/app  (base URL, 非 thread URL)
response_count_before_send: 0
response_count_after_error: 0    
send_without_new_response_start: true
error_type: GeminiFollowupSendUnconfirmed
```

### 3. 用户侧验证
用户确认 Gemini 创建了 thread `https://gemini.google.com/app/c64c669f984955b3`，但该 conversation **没有附件**。

## 修复项

| 修复 | 提交 | 位置 | 说明 |
|------|------|------|------|
| follow-up guard 添加 thread URL 检查 | `58d4dfc` | L2487, L2498 | 只有真正的 thread URL 才触发 guard，bare `/app` 跳过 |
| zip 展开扩展到普通 ask | `8850051` | `_prepare_gemini_file_paths_for_upload` | 新增 `CHATGPTREST_GEMINI_EXPAND_ZIP_ALWAYS=true` |
| 回归测试 | `58d4dfc` | `test_gemini_followup_wait_guard.py` | `test_gemini_bare_app_url_does_not_trigger_followup_guard` |

## 待跟进

1. **driver 侧日志增强**：记录 Drive picker 交互每一步的状态，以最终确认附件插入失败的具体子步骤
2. **`/app` URL 来源追踪**：为什么 driver 返回 bare `/app` 而非 thread URL — 可能是 Gemini 页面在文件处理期间未完成创建 thread
