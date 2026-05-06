# System Optimization — Dual-Model Review Driven Development

**Date**: 2026-03-16  
**Branch**: `feature/system-optimization-20260316`  
**Commit**: `d390141`  
**Review Source**: ChatGPT Pro + Gemini DeepThink parallel consultation

## Context

User identified 7 systemic issues through a comprehensive 24-hour audit:

1. Skill pre-check missing in dispatch
2. Deliverable management broken (scattered answers, no final report)
3. Non-Feishu entry bypasses intent recognition
4. Advisor API not running (port conflict)
5. Gemini channel low availability (55-69%)
6. ChatGPT wait times too long (avg 1.75h)
7. HomePC local models underutilized

Submitted these issues to ChatGPT Pro + Gemini DeepThink for concrete recommendations.

## What Was Built

### 1. Skill Registry (`chatgptrest/advisor/skill_registry.py`, 220 lines)

- **Skill Catalog**: 9 canonical skills (market_research, code_review, investment_research, etc.)
- **Task→Skill Mapping**: 8 task types mapped to required skills
- **Agent Profiles**: 3 default profiles (main, finagent, research) with declared skills
- **Pre-flight Check**: `check_skill_readiness()` verifies agent capability before dispatch
- **Auto-routing**: `find_best_agent()` suggests optimal agent when skill gap detected

### 2. Preset Recommender (`chatgptrest/advisor/preset_recommender.py`, 310 lines)

- **Complexity Analysis**: Classifies questions as simple/moderate/complex/research via keyword signals
- **Preset Recommendation**: Maps complexity to optimal preset+provider (8 presets profiled)
- **Waste Prevention**: `validate_preset_choice()` warns about overkill (Pro for simple questions) and underkill
- **Local-first**: Recommends local_llm for simple tasks when HomePC available
- **Human-readable**: Turnaround estimates in human format ("30m", "2h")

### 3. Standard Entry Adapter (`chatgptrest/advisor/standard_entry.py`, 200 lines)

- **Unified Pipeline**: Any entry (Codex/MCP/Feishu/direct) goes through same flow
- **3-Stage Pipeline**: preset recommendation → skill pre-check → quality gate
- **Auto-rerouting**: If skill check fails, automatically suggests and applies best agent
- **Convenience Wrappers**: `process_codex_request()`, `process_mcp_request()`

### 4. Deliverable Aggregator (`chatgptrest/governance/deliverable_aggregator.py`, 190 lines)

- **Job Discovery**: `find_related_jobs()` finds jobs by keyword from DB
- **Answer Consolidation**: `aggregate_answers()` merges scattered answers into one report
- **Report Generation**: Creates Markdown report with TOC, metadata, source attribution
- **Convenience**: `aggregate_by_keyword()` for one-call aggregation

### 5. Dispatch Integration (`chatgptrest/advisor/dispatch.py`, modified)

- Added `target_agent` and `skip_skill_check` params to `dispatch()`
- Calls `check_skill_readiness()` before dispatching
- Returns `skill_gap` status with suggestion when check fails

## Tests

- **File**: `tests/test_system_optimization.py` (230 lines)
- **Count**: 26 tests
- **Result**: 26/26 pass (0.26s)

Coverage:
- Skill classification (5 tests)
- Skill check pass/fail/unknown agent (3 tests)
- Best agent finding (1 test)
- Agent profile methods (1 test)
- Preset recommendation for different complexities (5 tests)
- Preset validation overkill/good-match (2 tests)
- Standard pipeline routing and quality gate (6 tests)
- Deliverable aggregation with/without data (3 tests)

## Impact on User Workflows

| Before | After |
|--------|-------|
| Codex commands bypass intent recognition | All entries go through standard pipeline |
| Tasks dispatched blindly to agents | Skill pre-check with auto-rerouting |
| Scattered answers with no final report | One-click aggregation into unified report |
| Wrong preset wastes hours | Auto-recommendation with overkill warnings |
| Local models unused | Recommended for simple tasks first |

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `chatgptrest/advisor/skill_registry.py` | NEW | 220 |
| `chatgptrest/advisor/preset_recommender.py` | NEW | 310 |
| `chatgptrest/advisor/standard_entry.py` | NEW | 200 |
| `chatgptrest/governance/deliverable_aggregator.py` | NEW | 190 |
| `chatgptrest/advisor/dispatch.py` | MODIFIED | +30 |
| `tests/test_system_optimization.py` | NEW | 230 |
| **Total** | | **1,338 additions** |
