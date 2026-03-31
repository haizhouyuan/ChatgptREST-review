這份《Harvester Worker + 品質門禁+ 指標看板》方案設計紮實，透過將「答案提取」邏輯從執行器解耦為獨立worker，大幅提升了系統的穩定性和審計能力。

以下是針對此方案的深入評審報告。

1. Must-fix (P0/P1)
P0：原子性寫衝突與狀態競爭(Race Condition)

問題描述：當前waitworker 在監測到done=true時會直接寫入answer.md。如果引入harvesterworker 同時處理該Job，可能會出現兩個進程同時寫入同一個檔案導致損壞。

修復要求：必須定義明確的Authoritative Hand-off。在Phase H1 以後，waitworker 僅負責寫入原始快照（如answer_raw.txt），而只有harvester被允許呼叫finalize_job()寫入最終的answer.md並標記Job 為completed。

P0：狀態儲存的「單點真理」 (Single Source of Truth)

問題描述：方案中提到harvest_state是DB 還是檔案作為Open Decision。

修復要求：必須選擇“DB 欄位為主，文件鏡像為輔”。在多worker 部署環境下，僅靠檔案鎖無法保證可審計的互信。必須在jobs表增加harvest_status字段，以支援原子的SELECT FOR UPDATE搶佔邏輯，防止重複收割。

P1：Gemini/Qwen 的一致性降級風險

問題描述：ChatGPT 有answer_id重構路徑，但Gemini/Qwen 往往只能依賴*_wait輪詢結果。

修復要求：對於缺乏匯出（Export）能力的Provider，品質門禁需增加「多點快照對比」。如果連續兩次輪詢結果長度波動（或縮水），門禁必須強制標記為deferred（推遲），而非盲目accept，以防收錄截斷的答案。

P1：熔斷器狀態同步(Circuit Breaker Sync)

問題描述：方案提到harvest_blocked_circuit_open事件。

修復要求：Harvester 的熔斷邏輯必須直接讀取chatgpt_blocked_state.json等現有驅動狀態檔。不能由Harvester 自己去猜測Provider 是否被封禁，否則會產生重複的UI 偵測，增加被封風險。

2. 建議優化

分源權重評分(Weighted Scoring)：不要只依賴單一分數。建議給不同來源設定基準權重：Rehydration (0.95) > Export (0.85) > Wait Poll (0.7) > DOM Fallback (0.5)。

強制「Deep Research」二次覆核：針對deep_research=true的Job，Harvester 必須強制驗證是否有「思考鏈（Thinking）」標記。如果收割到的答案只有結果而無思考過程，應判定為收割失敗。

支援「答案拼接」 (Heuristic Merging)：在deferred狀態下，如果發現兩次收割的內容是連續的（例如SSE 截斷），Harvester 可以嘗試在記憶體中拼接，但這需要極高的校驗強度。

影子模式的資料持久化：在Phase H0 (Shadow Mode) 期間，建議將Harvester 計算的結果存入answer_harvester_draft.md，方便人工通過diff工具與當前answer.md進行大規模比對。

看板增加「收割挽救率」指標：統計% of jobs that would have been failed/truncated but were saved by Harvester。這是證明該方案價值的核心ROI 指標。

3. 風險清單(上線前必讀)

UI 探測過載風險：DOM​​ Markdown Fallback 涉及Playwright 動作。如果Job 數量龐大，Harvester 可能觸發高頻的CDP 調用，導致瀏覽器效能下降或被風控識別。

陳舊資料覆蓋風險：如果wait階段已經產生了一個較好的本地答案，但Harvester 從伺服器導出的結果由於快取原因版本較舊，可能會導致答案「倒退」。

死循環風險：如果min_chars設定不合理（例如模型確實只回了一句話），Harvester 可能陷入defer -> retry的死循環，直到消耗完所有attempt。

4. 測試補充清單

[ ] 截斷恢復測試：模擬*_wait返回500 字符，但conversation_export返回2000 字符，驗證Harvester 能否正確「覆蓋升級」。

[ ] 衝突兜底測試：模擬answer_id對應的區塊已過期（404），驗證Harvester 能否平滑降級到DOM Fallback。

[ ] 並發搶佔測試：啟動3 個harvester實例，針對同一Job 進行收割，驗證資料庫行鎖是否生效，無重複事件產生。

[ ] 品質門禁負向測試：提供包含Thinking...或Tool Call Ack的無意義stub，驗證門禁是否能準確執行reject。

5. 結論：是否建議推進？

結論：是。

該方案是ChatgptREST 邁向「生產級可靠」的關鍵一步。

推進條件：

明確DB 鎖定邏輯：解決多worker 競爭問題。

強制唯讀約束：確保harvester權限集嚴格受限於READ-ONLY驅動工具。

完成Phase H0 觀察：至少在Shadow Mode 運行24h，且收割成功率（Finalize Success）需在所有鏈路上> 95% 方可開啟Phase H1。

後續行動： 如果你需要，我可以為你起草harvest_state_json的詳細資料庫Schema或品質門禁的具體評分演算法(Python 偽代碼)。
