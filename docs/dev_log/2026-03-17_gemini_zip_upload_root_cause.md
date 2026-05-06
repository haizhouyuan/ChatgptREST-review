# Gemini Zip 上传失败根因报告

**Job**: `0d44c139965c4d5a848b8a7f790aa230`  
**日期**: 2026-03-17  

## 结论

**Drive 上传成功，driver send 阶段失败。** zip 文件已正确上传到 Google Drive，但 Gemini Web Driver 在将 Drive 文件附入 Gemini 对话时超时，未能检测到新 response 开始。

## 证据链

### 1. Drive 上传 ✅
```
drive_id: 1EEYmtl5UKJpCU9FRA6klFt8eJFkm_bsh
drive_url: https://drive.google.com/open?id=1EEYmtl5UKJpCU9FRA6klFt8eJFkm_bsh
upload_completed: True
size_bytes: 110103
rclone lsjson elapsed: 2.958s, returncode: 0
```

### 2. Driver Send ❌
```
conversation_url: https://gemini.google.com/app  (base URL, 非 thread URL)
response_count_before_send: 0
response_count_after_error: 0    
send_without_new_response_start: true
elapsed_seconds: 72.343
```

### 3. 故障触发路径
`gemini_web_mcp.py` L2487-2507:
- `send_without_new_response_start=True` → 表示 driver 发送了 prompt 但未检测到 Gemini 开始新回复
- `initial_conversation_url` 非空（`/app`）→ guard 激活
- 输出 `GeminiFollowupSendUnconfirmed` + `needs_followup`

### 4. 用户侧验证
用户确认 Gemini 实际创建了 thread `https://gemini.google.com/app/c64c669f984955b3`，但该 conversation **没有附件**。说明 Drive 文件确实上传了，但 Gemini UI 自动化在"从云端硬盘添加"步骤未能完成附件插入。

## 根因

Gemini CDP 自动化（driver 侧）在处理 Drive 附件时可能存在以下问题之一：
1. **"从云端硬盘添加" UI 交互超时** — Gemini 的 Drive picker 弹窗 CDP 定位失败
2. **zip 格式不被 Gemini Drive picker 识别** — 可能只显示 docs/sheets/slides
3. **附件插入后 prompt box 状态变化未被 driver 检测到** — driver 以为 send 失败

## 修复项

| 修复 | 位置 | 说明 |
|------|------|------|
| zip 预解压 | `_prepare_gemini_file_paths_for_upload` | 将 .zip 解压为独立文件后分别上传 |
| 日志增强 | driver 侧 `gemini_web_ask` | 记录 Drive picker 交互每一步的状态 |
| send 超时延长 | `send_timeout_seconds` | 对有附件的请求预留更长发送时间（当前 70s 不够）|
