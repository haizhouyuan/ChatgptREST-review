# Finbot 上线监控日志 (2026-03-16)

## 启动检查 @ 21:39

### 服务状态
| 服务 | 状态 | 启动时间 |
|------|------|---------|
| chatgptrest-api | ✅ active | 21:10:35 |
| chatgptrest-worker-send | ✅ active | 21:10:35 |
| chatgptrest-worker-wait | ✅ active | 21:10:35 |
| openclaw-gateway | ✅ active | 21:14:03 |
| finbot timers | ❓ 0 loaded | 需调查 |

### Ops 概览
- in_progress: 7 jobs
- completed: 6612
- error: 610
- stale: 0
- ui_canary: ✅ OK
- build: c3a225b19e5b (clean)

### 活跃 Job 初始状态 @ 21:39
| Job ID (短) | 任务 | Phase | Detail | 已有对话 |
|------------|------|-------|--------|---------|
| 6ec7 | 三轮总报告替代版 | wait | awaiting_assistant_answer | ✅ 15.8k chars |
| 8efa | 小牛单品牌深研 | wait | awaiting_assistant_answer | ✅ 14.0k chars |
| c0b0 | 春风动力单品牌深研 | wait | awaiting_assistant_answer | ❌ 无 export |
| 3368 | 金固切入策略综合分析 | wait | awaiting_assistant_answer | ✅ 19.1k chars |

### 发现的问题
- [P1] finbot timers 显示 0 loaded units — 用户称已激活
- [P2] c0b0 (春风动力) 无 conversation export 数据
- [P3] 610 error jobs 历史积累（需确认是否与当前 merge 相关）

---

## 轮次检查记录

_(后续检查将追加在此)_
