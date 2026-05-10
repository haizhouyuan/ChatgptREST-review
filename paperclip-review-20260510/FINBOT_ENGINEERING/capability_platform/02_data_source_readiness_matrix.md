# 02 Data Source Readiness Matrix

Generated: `2026-05-09T17:55:49+08:00`

| Source | Category | Status | Proof | Allowed | Disallowed |
| --- | --- | --- | --- | --- | --- |
| SEC EDGAR submissions | US/global primary evidence | workflow_verified | workflow_verified | primary evidence lookup, filing update alerts | advice, trading, broker action |
| SEC companyfacts | US/global primary evidence | workflow_verified | workflow_verified | company fundamentals and evidence binding | price signal or target-price output |
| issuer IR pages | US/global primary evidence | candidate_to_enable | not_verified | candidate for primary evidence after smoke | workflow use before read-only smoke |
| earnings releases / filings | US/global primary evidence | workflow_verified | workflow_verified | primary evidence lookup and filing alert | earnings surprise trading signal |
| Form 4 | US/global primary evidence | configured_but_unverified | surface_route_only | ownership/catalyst context after smoke | real-time insider trade signal |
| 13F as ownership context only | US/global primary evidence | configured_but_unverified | surface_route_only | ownership context with 45-day lag label | current-holding claim or follow-trade use |
| Alpaca watch-only | Market data / price context | candidate_to_enable | not_verified | watch-only market context after workflow proof | orders, account, broker action, trade signal |
| OpenBB if available | Market data / price context | candidate_to_enable | not_verified | candidate data access after install/smoke approval | unverified production data feed |
| local price CSV fixture fallback | Market data / price context | workflow_verified | workflow_verified | prototype valuation context and validator tests | live price readiness claim |
| public exchange pages where legal and capturable | Market data / price context | candidate_to_enable | not_verified | candidate exchange context after legal/read-only review | automated scraping without governance |
| Binance risk context | Market data / price context | candidate_to_enable | not_verified | candidate crypto risk context after approval and read-only smoke | mainline source, trading, broker/account action, trade signal, or workflow_verified claim before proof |
| Daloopa | Fundamentals / KPI / transcripts | candidate_to_enable | not_verified | candidate KPI after approval and smoke | claiming current workflow verification |
| Quartr | Fundamentals / KPI / transcripts | candidate_to_enable | not_verified | candidate transcript/IR after approval and smoke | claiming current workflow verification |
| SEC filings | Fundamentals / KPI / transcripts | workflow_verified | workflow_verified | company fundamentals, evidence, stale-filing alerts | investment conclusion without review |
| company IR | Fundamentals / KPI / transcripts | candidate_to_enable | not_verified | candidate after capture protocol | unverified transcript workflow |
| Readwise | Knowledge / source tracking | candidate_to_enable | not_verified | candidate source discovery after approval | authority evidence or production ingestion before smoke |
| Zotero | Knowledge / source tracking | candidate_to_enable | not_verified | candidate document store after approval | claiming current lane availability |
| Google Drive / local docs | Knowledge / source tracking | workflow_verified | workflow_verified | local evidence and historical-method intake | assuming Drive remote connector availability |
| web-content-extractor / governed local HTML extraction | Knowledge / source tracking | workflow_verified | workflow_verified | evidence capture/excerpt from approved artifacts | unapproved scraping or quarantined provider extraction |
| Chrome DevTools / CDP evidence capture | Knowledge / source tracking | tool_callable_only | tool_callable_only | candidate manual evidence capture after Governance protocol | workflow_verified claim without smoke |
| CNINFO | A-share / China route candidates | candidate_to_enable | not_verified | future official A-share evidence | current workflow claim |
| SSE | A-share / China route candidates | candidate_to_enable | not_verified | future official A-share evidence | current workflow claim |
| SZSE | A-share / China route candidates | candidate_to_enable | not_verified | future official A-share evidence | current workflow claim |
| BSE | A-share / China route candidates | candidate_to_enable | not_verified | future official A-share evidence | current workflow claim |
| AKShare | A-share / China route candidates | candidate_to_enable | not_verified | future DataContract-backed A-share research | production data without PIT/field contract |
| Tushare | A-share / China route candidates | candidate_to_enable | not_verified | future DataContract-backed A-share research | credential use without approval |
| Baostock | A-share / China route candidates | candidate_to_enable | not_verified | future backtest research after PIT review | validated signal before proof |
| Eastmoney / Tonghuashun downgraded secondary routes | A-share / China route candidates | candidate_to_enable | not_verified | secondary context with primary corroboration | authority evidence or automated scrape without legal review |
| TradingAgents / TradingAgents-CN | Research and validation frameworks | candidate_to_enable | method_reference_only | method reference only | runtime authority or advice engine |
| Fincept | Research and validation frameworks | candidate_to_enable | method_reference_only | UX/workbench reference only | decision authority |
| Qlib / vectorbt / Backtrader / Lean | Research and validation frameworks | candidate_to_enable | not_verified | future signal research with PIT fixtures | approved signal without backtest proof |
| LangGraph / Agno / PydanticAI | Research and validation frameworks | candidate_to_enable | method_reference_only | future controlled workflow design | runtime mutation without approval |
| MiniMax / DeepSeek / Tavily / Brave | Provider quarantine | quarantined_or_no_production_use | no_production_use | none in this phase | any production/research execution path |
