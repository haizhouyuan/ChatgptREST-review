from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatgptrest import finbot
from chatgptrest.kernel.llm_connector import LLMResponse


def test_finbot_watchlist_scout_writes_pending_inbox_item(tmp_path: Path, monkeypatch) -> None:
    def _fake_snapshot(**_: object) -> dict[str, object]:
        return {
            "scope": "today",
            "priority_targets": [
                {
                    "thesis_id": "transformer-supercycle",
                    "thesis_title": "变压器超级周期",
                    "target_case_id": "tc_transformer_tbea",
                    "action_state": "starter",
                    "validation_state": "evidence_backed",
                    "reason": "订单交期仍在高位。",
                }
            ],
            "queue_summary": {"decision_maintenance": 3, "review_remediation": 0},
            "summary": {"theses": 14},
            "top_theses": [{"thesis_id": "transformer-supercycle"}],
        }

    monkeypatch.setattr(finbot, "_run_finagent_snapshot", _fake_snapshot)

    payload = finbot.watchlist_scout(root=tmp_path)

    assert payload["ok"] is True
    assert payload["created"] is True
    assert payload["item_id"].startswith("finbot-watchlist-")
    json_path = Path(payload["json_path"])
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["category"] == "watchlist_scout"
    assert saved["source"] == "finagent.integration_snapshot"


def test_finbot_lane_rejects_empty_openrouter_text(monkeypatch) -> None:
    class _StubConnector:
        def ask(self, *_: object, **__: object) -> LLMResponse:
            return LLMResponse(
                text="",
                provider="openrouter/nvidia/nemotron-3-super-120b-a12b:free",
                preset="planning",
                status="success",
            )

    monkeypatch.setenv("FINBOT_TIER", "free")
    monkeypatch.setattr(finbot, "_coding_plan_connector", lambda: _StubConnector())

    with pytest.raises(RuntimeError, match="empty text"):
        finbot._ask_coding_plan_lane(
            lane_slug="claim",
            system_prompt="sys",
            prompt="user",
        )


def test_finbot_theme_radar_scout_writes_pending_inbox_item(tmp_path: Path, monkeypatch) -> None:
    def _fake_radar(**_: object) -> dict[str, object]:
        return {"summary": {"radar_items": 2}, "items": []}

    def _fake_inbox(**_: object) -> dict[str, object]:
        return {
            "items": [
                {
                    "candidate_id": "candidate_tsmc_cpo",
                    "thesis_name": "TSMC CPO packaging capacity ramp",
                    "residual_class": "frontier",
                    "route": "opportunity",
                    "ranking_score": 0.72,
                    "next_action": "keep_scanning",
                    "note": "CoWoS 专线扩产可能成为新的 CPO 配套瓶颈。",
                    "attention_capture_ratio": 0.5,
                }
            ]
        }

    monkeypatch.setattr(finbot, "_run_theme_radar_board", _fake_radar)
    monkeypatch.setattr(finbot, "_run_opportunity_inbox", _fake_inbox)
    monkeypatch.setattr(finbot, "_run_kol_suite", lambda **_: {"ok": True, "suite_slug": "suite-1"})
    monkeypatch.setattr(
        finbot,
        "_ask_coding_plan_lane",
        lambda **kwargs: {
            "provider": "coding_plan/MiniMax-M2.5",
            "preset": "planning",
            "latency_ms": 10.0,
            "structured": (
                {
                    "core_claims": ["TSMC CPO 配套条件正在形成"],
                    "supporting_evidence": ["TSMC IR 提到封装资源持续偏紧"],
                    "critical_unknowns": ["真实客户吸收节奏"],
                    "key_sources": ["TSMC IR"],
                    "absorption_candidates": ["硅光 / CPO"],
                }
                if kwargs.get("lane_slug") == "claim"
                else {
                    "bear_case": "量产时点继续后移。",
                    "thesis_breakers": ["海外玩家先拿到商业部署"],
                    "timing_risks": ["1.6T 放量晚于预期"],
                    "competing_paths": ["Broadcom 直接推进现有路线"],
                    "disconfirming_signals": ["Bailly 延期"],
                }
                if kwargs.get("lane_slug") == "skeptic"
                else {
                    "leader": "中际旭创",
                    "ranked_expressions": [
                        {"rank": 1, "expression": "中际旭创", "why_best": "先吃 800G/1.6T core 兑现", "why_not_best": "", "readiness": "prepare"},
                        {"rank": 2, "expression": "Broadcom", "why_best": "平台能力强", "why_not_best": "中国表达不直接", "readiness": "watch"},
                    ],
                    "comparison_logic": ["先配 core，再观察 option"],
                }
            ),
            "markdown": "lane markdown",
        },
    )
    monkeypatch.setattr(
        finbot,
        "_ask_coding_plan_dossier",
        lambda **_: {
            "provider": "coding_plan/MiniMax-M2.5",
            "preset": "planning",
            "latency_ms": 12.0,
            "structured": {
                "headline": "TSMC CPO 深挖",
                "current_decision": "deepen_now",
                "thesis_status": "promising",
                "best_absorption_theme": "硅光 / CPO",
                "best_expression_today": "中际旭创",
                "why_not_investable_yet": "需要更多产能验证",
                "next_proving_milestone": "TSMC confirms dedicated CPO capacity lane",
                "forcing_events": [],
                "disconfirming_signals": [],
                "key_sources": ["TSMC IR"],
                "research_gaps": [],
            },
            "markdown": "## One-line judgment\n继续深挖。\n",
        },
    )

    class _StubDashboardService:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def investor_snapshot(self) -> dict[str, object]:
            return {
                "opportunities": [
                    {
                        "candidate_id": "candidate_tsmc_cpo",
                        "thesis_name": "TSMC CPO packaging capacity ramp",
                        "route": "opportunity",
                        "residual_class": "frontier",
                        "ranking_score": 0.72,
                        "note": "CoWoS 专线扩产可能成为新的 CPO 配套瓶颈。",
                        "brief_next_action": "deepen_now",
                        "brief_next_proving_milestone": "TSMC confirms dedicated CPO capacity lane",
                        "related_themes": [
                            {
                                "theme_slug": "silicon_photonics",
                                "title": "硅光 / CPO",
                                "detail_href": "/v2/dashboard/investor/themes/silicon_photonics",
                                "best_expression": "中际旭创",
                            }
                        ],
                        "suggested_sources": ["TSMC IR"],
                    }
                ],
                "strong_sources": [
                    {
                        "name": "TSMC IR",
                        "source_type": "official_disclosure",
                        "source_trust_tier": "anchor",
                        "track_record_label": "emerging",
                        "accepted_route_count": 10,
                        "validated_case_count": 2,
                        "detail_href": "/v2/dashboard/investor/sources/src-tsmc",
                    }
                ],
                "kols": [],
                "planning_doc_reader_href": "/v2/dashboard/reader?path=/allowed/planning.md",
                "planning_doc_path": "/allowed/planning.md",
                "themes": [
                    {
                        "theme_slug": "silicon_photonics",
                        "title": "硅光 / CPO",
                        "detail_href": "/v2/dashboard/investor/themes/silicon_photonics",
                        "best_expression": "中际旭创",
                        "related_opportunities": [{"candidate_id": "candidate_tsmc_cpo"}],
                        "related_sources": ["TSMC IR", "Broadcom / TSMC CPO"],
                    }
                ]
            }

        def investor_theme_detail(self, theme_slug: str) -> dict[str, object]:
            assert theme_slug == "silicon_photonics"
            return {
                "theme": {"theme_slug": "silicon_photonics", "title": "硅光 / CPO", "recommended_posture": "watch_with_prepare_candidate", "best_expression": "中际旭创"},
                "detail": {
                    "investor_question": "当前最值得准备的表达是什么？",
                    "thesis_statement": "核心和 option 要拆开。",
                    "why_now": "1.6T 开始兑现。",
                    "why_mispriced": "市场把 core 和 option 混着定价。",
                    "decision_card": {
                        "decision_excerpt": "准备 core，不追 option。",
                        "investor_excerpt": "当前先看 core。",
                        "capital_gate": ["1.6T 继续兑现"],
                        "stop_rule": ["option 长期不兑现"],
                        "thesis_level_falsifiers": ["海外玩家先商业化"],
                        "timing_level_falsifiers": ["1.6T 放缓"],
                    },
                },
            }

    monkeypatch.setattr(finbot, "DashboardService", _StubDashboardService)

    payload = finbot.theme_radar_scout(root=tmp_path)

    assert payload["ok"] is True
    assert payload["created"] is True
    assert payload["item_id"].startswith("finbot-radar-")
    saved = json.loads(Path(payload["json_path"]).read_text(encoding="utf-8"))
    assert saved["category"] == "theme_radar"
    assert saved["source"] == "finagent.theme_radar"
    assert payload["deepening_brief"]["created"] is True
    brief = json.loads(Path(payload["deepening_brief"]["json_path"]).read_text(encoding="utf-8"))
    assert brief["category"] == "deepening_brief"
    assert brief["payload"]["related_themes"][0]["theme_slug"] == "silicon_photonics"
    assert payload["research_package"]["created"] is True
    latest = Path(payload["research_package"]["package"]["json_path"])
    saved_package = json.loads(latest.read_text(encoding="utf-8"))
    assert saved_package["candidate_id"] == "candidate_tsmc_cpo"
    assert saved_package["best_expression_today"] == "中际旭创"
    assert saved_package["lanes"]["claim"]["core_claims"][0] == "TSMC CPO 配套条件正在形成"
    assert saved_package["lanes"]["expression"]["leader"] == "中际旭创"
    assert saved_package["claim_objects"][0]["claim_id"].startswith("clm_")
    assert saved_package["citation_objects"][0]["citation_id"].startswith("cit_")
    assert saved_package["claim_citation_edges"][0]["claim_id"] == saved_package["claim_objects"][0]["claim_id"]
    assert saved_package["source_scorecard"][0]["name"] == "TSMC IR"
    assert saved_package["source_scorecard"][0]["contribution_role"] == "anchor"
    source_scores = json.loads((tmp_path / "source_scores" / "latest.json").read_text(encoding="utf-8"))
    assert source_scores["sources"][0]["name"] == "TSMC IR"
    assert source_scores["sources"][0]["supported_claim_count"] >= 1


def test_finbot_theme_batch_run_writes_pending_items(tmp_path: Path, monkeypatch) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "themes": [
                    {
                        "theme_slug": "transformer",
                        "title": "变压器超级周期",
                        "spec_path": "spec.yaml",
                        "events_path": "events.json",
                        "as_of": "2026-03-15",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def _fake_run(**_: object) -> dict[str, object]:
        return {
            "theme_slug": "transformer",
            "recommended_posture": "watch_with_prepare_candidate",
            "best_expression": {
                "projection_id": "sntl_xidian_alt",
                "entity": "中国西电",
                "product": "UHV 一次设备",
                "recommended_action": "prepare_candidate",
                "evidence_quality_band": "strong",
                "constraint_burden": 0.1,
            },
            "run_root": "/tmp/transformer",
        }

    monkeypatch.setattr(finbot, "_run_finagent_script_json", _fake_run)

    payload = finbot.theme_batch_run(root=tmp_path, catalog_path=catalog_path, limit=3)

    assert payload["ok"] is True
    assert payload["theme_count"] == 1
    assert len(payload["created_items"]) == 1
    saved = json.loads(Path(payload["created_items"][0]["json_path"]).read_text(encoding="utf-8"))
    assert saved["category"] == "theme_run"
    assert saved["source"] == "finagent.event_mining.theme_suite"
    theme_state = json.loads((tmp_path / "themes" / "transformer" / "latest.json").read_text(encoding="utf-8"))
    assert theme_state["best_expression"] == "中国西电"
    assert theme_state["history"]["status"] == "new"


def test_finbot_daily_work_composes_refresh_watchlist_and_radar(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(finbot, "refresh_dashboard_projection", lambda **_: {"ok": True, "refresh_status": "ok"})
    monkeypatch.setattr(finbot, "_run_finagent_daily_refresh", lambda **_: {"ok": True, "fetch_success": 3, "fetch_failed": 0})
    monkeypatch.setattr(finbot, "watchlist_scout", lambda **_: {"ok": True, "created": True, "item_id": "watch-1"})
    monkeypatch.setattr(finbot, "theme_radar_scout", lambda **_: {"ok": True, "created": False})
    monkeypatch.setattr(finbot, "theme_batch_run", lambda **_: {"ok": True, "created_items": [{"item_id": "theme-1"}]})

    payload = finbot.daily_work(root=tmp_path, include_theme_batch=True, include_market_discovery=False)

    assert payload["ok"] is True
    assert payload["refresh"]["refresh_status"] == "ok"
    assert payload["source_refresh"]["fetch_success"] == 3
    assert payload["watchlist"]["item_id"] == "watch-1"
    assert payload["created_count"] == 2
    assert payload["theme_batch"]["created_items"][0]["item_id"] == "theme-1"


def test_finbot_daily_work_continues_when_source_refresh_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(finbot, "refresh_dashboard_projection", lambda **_: {"ok": True, "refresh_status": "ok"})
    monkeypatch.setattr(finbot, "_run_finagent_daily_refresh", lambda **_: (_ for _ in ()).throw(RuntimeError("refresh boom")))
    monkeypatch.setattr(finbot, "watchlist_scout", lambda **_: {"ok": True, "created": False})
    monkeypatch.setattr(finbot, "theme_radar_scout", lambda **_: {"ok": True, "created": True, "item_id": "radar-1"})

    payload = finbot.daily_work(root=tmp_path, include_theme_batch=False, include_market_discovery=False)

    assert payload["ok"] is True
    assert payload["source_refresh"]["ok"] is False
    assert "refresh boom" in payload["source_refresh"]["error"]
    assert payload["theme_radar"]["item_id"] == "radar-1"
    assert payload["created_count"] == 1


def test_finbot_ack_inbox_item_moves_files_to_archive(tmp_path: Path) -> None:
    item = finbot.InboxItem(
        item_id="finbot-watchlist-demo",
        created_at=1.0,
        title="demo",
        summary="summary",
        category="watchlist_scout",
        severity="accent",
        source="test",
        action_hint="read it",
        payload={},
    )
    write_payload = finbot.write_inbox_item(item, root=tmp_path)
    json_path = Path(write_payload["json_path"])
    assert json_path.exists()

    result = finbot.ack_inbox_item(item.item_id, root=tmp_path)

    assert result["ok"] is True
    assert not json_path.exists()
    assert Path(result["archived_json"]).exists()


def test_finbot_opportunity_deepen_writes_dossier_and_inbox(tmp_path: Path, monkeypatch) -> None:
    class _StubDashboardService:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def investor_snapshot(self) -> dict[str, object]:
            return {
                "opportunities": [
                    {
                        "candidate_id": "candidate_tsmc_cpo",
                        "thesis_name": "TSMC CPO packaging capacity ramp",
                        "route": "opportunity",
                        "residual_class": "frontier",
                        "ranking_score": 0.72,
                        "note": "CoWoS 专线扩产可能成为新的 CPO 配套瓶颈。",
                        "brief_next_action": "deepen_now",
                        "brief_next_proving_milestone": "TSMC confirms dedicated CPO capacity lane",
                        "related_themes": [
                            {
                                "theme_slug": "silicon_photonics",
                                "title": "硅光 / CPO",
                                "detail_href": "/v2/dashboard/investor/themes/silicon_photonics",
                                "best_expression": "中际旭创",
                            }
                        ],
                        "suggested_sources": ["TSMC IR"],
                    }
                ],
                "strong_sources": [
                    {
                        "name": "TSMC IR",
                        "source_type": "official_disclosure",
                        "source_trust_tier": "anchor",
                        "track_record_label": "emerging",
                        "accepted_route_count": 10,
                        "validated_case_count": 2,
                        "detail_href": "/v2/dashboard/investor/sources/src-tsmc",
                    }
                ],
                "kols": [],
                "planning_doc_reader_href": "/v2/dashboard/reader?path=/allowed/planning.md",
                "planning_doc_path": "/allowed/planning.md",
            }

        def investor_theme_detail(self, theme_slug: str) -> dict[str, object]:
            assert theme_slug == "silicon_photonics"
            return {
                "theme": {"theme_slug": "silicon_photonics", "title": "硅光 / CPO", "recommended_posture": "watch_with_prepare_candidate", "best_expression": "中际旭创"},
                "detail": {
                    "investor_question": "当前最值得准备的表达是什么？",
                    "thesis_statement": "核心和 option 要拆开。",
                    "why_now": "1.6T 开始兑现。",
                    "why_mispriced": "市场把 core 和 option 混着定价。",
                    "decision_card": {
                        "decision_excerpt": "准备 core，不追 option。",
                        "investor_excerpt": "当前先看 core。",
                        "capital_gate": ["1.6T 继续兑现"],
                        "stop_rule": ["option 长期不兑现"],
                        "thesis_level_falsifiers": ["海外玩家先商业化"],
                        "timing_level_falsifiers": ["1.6T 放缓"],
                    },
                },
            }

    monkeypatch.setattr(finbot, "DashboardService", _StubDashboardService)
    monkeypatch.setattr(finbot, "_run_kol_suite", lambda **_: {"ok": True, "suite_slug": "finbot_candidate_tsmc_cpo", "consensus_topics": 2})
    monkeypatch.setattr(
        finbot,
        "_ask_coding_plan_lane",
        lambda **kwargs: {
            "provider": "coding_plan/MiniMax-M2.5",
            "preset": "planning",
            "latency_ms": 20.0,
            "structured": (
                {
                    "core_claims": ["CPO 配套瓶颈正在形成"],
                    "supporting_evidence": ["TSMC IR"],
                    "critical_unknowns": ["客户验证深度"],
                    "key_sources": ["TSMC IR"],
                    "absorption_candidates": ["硅光 / CPO"],
                    "claim_ledger": [
                        {
                            "claim": "TSMC CPO 专用封装能力正在形成",
                            "evidence_grade": "medium",
                            "importance": "high",
                            "why_it_matters": "决定 CPO 从验证走向试产的节奏。",
                            "next_check": "TSMC 下一次明确提到 CPO 产线规划。",
                        }
                    ],
                }
                if kwargs.get("lane_slug") == "claim"
                else {
                    "bear_case": "验证节奏继续向后拖。",
                    "thesis_breakers": ["海外先商业化"],
                    "timing_risks": ["H1 2026 风险量产延迟"],
                    "competing_paths": ["TH5 先走成熟架构"],
                    "disconfirming_signals": ["Bailly 继续延期"],
                    "risk_register": [
                        {
                            "risk": "可插拔模块继续压制 CPO 节奏",
                            "severity": "high",
                            "horizon": "12-18m",
                            "what_confirms": "云厂商继续优先采购 1.6T 可插拔",
                            "what_refutes": "中际旭创明确 CPO 收入时间表",
                        }
                    ],
                }
                if kwargs.get("lane_slug") == "skeptic"
                else {
                    "leader": "中际旭创",
                    "valuation_frame": {
                        "current_view": "先交易可插拔兑现，不提前透支 CPO 期权。",
                        "base_case": "800G 高出货 + 1.6T 小批量兑现",
                        "bull_case": "CPO 验证提前进入 pilot",
                        "bear_case": "CPO 延后且 1.6T ASP 下行",
                        "key_variable": "1.6T 占比与 CPO 验证节奏",
                    },
                    "ranked_expressions": [
                        {"rank": 1, "expression": "中际旭创", "why_best": "最接近中国可行动表达", "why_not_best": "", "readiness": "prepare", "valuation_anchor": "兑现先于重估", "scenario_base": "模块主线", "scenario_bull": "CPO 提前验证", "scenario_bear": "ASP 回落"},
                        {"rank": 2, "expression": "Broadcom", "why_best": "海外平台", "why_not_best": "不适合作为中国表达", "readiness": "watch"},
                    ],
                    "comparison_logic": ["核心表达优先于远期 option"],
                }
            ),
            "markdown": "lane markdown",
        },
    )
    monkeypatch.setattr(
        finbot,
        "_ask_coding_plan_dossier",
        lambda **_: {
            "provider": "coding_plan/MiniMax-M2.5",
            "preset": "planning",
            "latency_ms": 123.0,
            "structured": {
                "headline": "TSMC CPO 正在从信号走向研究件",
                "current_decision": "deepen_now",
                "thesis_status": "promising",
                "best_absorption_theme": "硅光 / CPO",
                "best_expression_today": "中际旭创",
                "why_not_investable_yet": "仍需等 TSMC 确认 CPO 专线和客户吸收路径。",
                "next_proving_milestone": "TSMC confirms dedicated CPO capacity lane",
                "forcing_events": ["TSMC 明确 CPO 产线", "Broadcom 商业化落地"],
                "disconfirming_signals": ["Bailly 继续延期"],
                "key_sources": ["TSMC IR"],
                "research_gaps": ["中国链表达仍需补全"],
            },
            "markdown": "## One-line judgment\n准备继续深挖。\n",
        },
    )

    result = finbot.opportunity_deepen(root=tmp_path, force=True)

    assert result["ok"] is True
    assert result["created"] is True
    latest = tmp_path / "opportunities" / "tsmc-cpo" / "latest.json"
    assert latest.exists()
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["best_expression_today"] == "中际旭创"
    assert payload["lanes"]["skeptic"]["bear_case"] == "验证节奏继续向后拖。"
    assert payload["lanes"]["expression"]["ranked_expressions"][0]["expression"] == "中际旭创"
    assert payload["lanes"]["claim"]["claim_ledger"][0]["evidence_grade"] == "medium"
    assert payload["lanes"]["claim"]["claim_ledger"][0]["claim_id"].startswith("clm_")
    assert payload["lanes"]["claim"]["claim_ledger"][0]["supporting_sources"][0]["name"] == "TSMC IR"
    assert payload["lanes"]["skeptic"]["risk_register"][0]["severity"] == "high"
    assert payload["lanes"]["expression"]["valuation_frame"]["key_variable"] == "1.6T 占比与 CPO 验证节奏"
    assert payload["source_scorecard"][0]["name"] == "TSMC IR"
    assert payload["source_scorecard"][0]["contribution_role"] == "anchor"
    assert payload["claim_objects"][0]["claim_text"] == "TSMC CPO 专用封装能力正在形成"
    assert payload["claim_objects"][0]["falsification_condition"]
    assert payload["claim_objects"][0]["decision_relevance"] in {"decision_blocker", "supporting", "needs_proof"}
    assert payload["citation_objects"][0]["source_name"] == "TSMC IR"
    assert payload["citation_objects"][0]["quality_band"] in {"core", "useful", "monitor", "weak", ""}
    assert payload["claim_citation_edges"][0]["is_load_bearing"] in {True, False}
    assert payload["history"]["status"] == "new"
    assert "action_distance_after" in payload["history"]
    inbox_path = tmp_path / "inbox" / "pending" / "finbot-package-candidate-tsmc-cpo.json"
    assert inbox_path.exists()
    inbox_payload = json.loads(inbox_path.read_text(encoding="utf-8"))
    assert inbox_payload["category"] == "research_package"
    assert inbox_payload["payload"]["current_decision"] == "deepen_now"
    source_scores = json.loads((tmp_path / "source_scores" / "latest.json").read_text(encoding="utf-8"))
    assert source_scores["sources"][0]["quality_band"] in {"core", "useful", "monitor", "weak"}
    assert "load_bearing_claim_count" in source_scores["sources"][0]


def test_finbot_write_inbox_item_coalesces_same_logical_item(tmp_path: Path) -> None:
    legacy = {
        "item_id": "finbot-radar-candidate-tsmc-cpo-legacy",
        "created_at": 0.5,
        "title": "legacy radar",
        "summary": "legacy",
        "category": "theme_radar",
        "severity": "accent",
        "source": "test",
        "action_hint": "review",
        "payload": {"logical_key": "candidate_tsmc_cpo", "candidate_id": "candidate_tsmc_cpo"},
    }
    pending = tmp_path / "inbox" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    (pending / "finbot-radar-candidate-tsmc-cpo-legacy.json").write_text(json.dumps(legacy), encoding="utf-8")
    (pending / "finbot-radar-candidate-tsmc-cpo-legacy.md").write_text("# legacy\n", encoding="utf-8")

    item = finbot.InboxItem(
        item_id="finbot-radar-candidate-tsmc-cpo",
        created_at=1.0,
        title="radar",
        summary="summary-a",
        category="theme_radar",
        severity="accent",
        source="test",
        action_hint="review",
        payload={"logical_key": "candidate_tsmc_cpo", "candidate_id": "candidate_tsmc_cpo"},
    )
    first = finbot.write_inbox_item(item, root=tmp_path)
    archived = tmp_path / "inbox" / "archived"
    assert any(path.name.startswith("finbot-radar-candidate-tsmc-cpo-legacy") for path in archived.glob("*.json"))
    second = finbot.write_inbox_item(item, root=tmp_path)
    assert first["created"] is True
    assert second["created"] is False
    assert second["updated"] is False

    changed = finbot.InboxItem(
        item_id=item.item_id,
        created_at=item.created_at,
        title=item.title,
        summary="summary-b",
        category=item.category,
        severity=item.severity,
        source=item.source,
        action_hint=item.action_hint,
        payload=item.payload,
    )
    third = finbot.write_inbox_item(changed, root=tmp_path)
    assert third["created"] is False
    assert third["updated"] is True
    saved = json.loads(Path(third["json_path"]).read_text(encoding="utf-8"))
    assert saved["summary"] == "summary-b"


# ---------------------------------------------------------------------------
# Phase 2: Belief Integrity — semantic reversal detection
# ---------------------------------------------------------------------------


class TestHasSemanticReversal:
    """Tests for _has_semantic_reversal() negation detector."""

    def test_growth_vs_decline(self) -> None:
        assert finbot._has_semantic_reversal("利润大幅增长", "利润大幅下滑") is True

    def test_bullish_vs_bearish(self) -> None:
        assert finbot._has_semantic_reversal("市场利好信号频现", "市场利空信号频现") is True

    def test_upgrade_vs_downgrade(self) -> None:
        assert finbot._has_semantic_reversal("评级升级", "评级降级") is True

    def test_reverse_direction_also_detected(self) -> None:
        # _ALL_DIRECTION_WORDS includes both directions
        assert finbot._has_semantic_reversal("利润下滑", "利润增长") is True

    def test_beat_vs_miss_expectations(self) -> None:
        assert finbot._has_semantic_reversal("业绩超预期", "业绩不及预期") is True

    def test_buy_vs_sell(self) -> None:
        assert finbot._has_semantic_reversal("建议买入", "建议卖出") is True

    def test_no_false_positive_for_similar_claims(self) -> None:
        # Both claims talk about growth — no reversal
        assert finbot._has_semantic_reversal("收入增长加速", "利润增长加速") is False

    def test_no_false_positive_for_unrelated(self) -> None:
        assert finbot._has_semantic_reversal("TSMC 扩产计划明确", "Broadcom 产品线推进") is False

    def test_empty_strings(self) -> None:
        assert finbot._has_semantic_reversal("", "利润增长") is False
        assert finbot._has_semantic_reversal("利润增长", "") is False
        assert finbot._has_semantic_reversal("", "") is False

    def test_optimistic_vs_pessimistic(self) -> None:
        assert finbot._has_semantic_reversal("管理层态度乐观", "管理层态度悲观") is True


class TestMatchPreviousClaimContradicted:
    """Tests for _match_previous_claim returning contradicted status."""

    def test_contradicted_when_semantic_reversal(self) -> None:
        row = {"claim": "公司利润大幅增长"}
        previous = [
            {
                "claim_id": "clm_old",
                "claim_text": "公司利润大幅下滑",  # opposite direction
                "evidence_grade": "high",
            }
        ]
        result = finbot._match_previous_claim(row, previous)
        assert result.get("_match_status") == "contradicted"
        assert result.get("claim_id") == "clm_old"

    def test_persistent_when_same_without_reversal(self) -> None:
        row = {"claim": "公司利润持续增长"}
        previous = [
            {
                "claim_id": "clm_old",
                "claim_text": "公司利润持续增长",  # identical
            }
        ]
        result = finbot._match_previous_claim(row, previous)
        assert "_match_status" not in result  # no contradicted tag
        assert result.get("claim_id") == "clm_old"

    def test_no_match_returns_empty(self) -> None:
        row = {"claim": "完全不同的话题"}
        previous = [
            {
                "claim_id": "clm_old",
                "claim_text": "公司利润大幅下滑",
            }
        ]
        result = finbot._match_previous_claim(row, previous)
        assert result == {}


# ---------------------------------------------------------------------------
# Phase 1: Market Truth — ticker inference + valuation frame
# ---------------------------------------------------------------------------


class TestInferMarketFromTicker:
    """Tests for _infer_market_from_ticker()."""

    def test_cn_with_suffix(self) -> None:
        assert finbot._infer_market_from_ticker("002025.SZ") == "CN"
        assert finbot._infer_market_from_ticker("600519.SH") == "CN"
        assert finbot._infer_market_from_ticker("430047.BJ") == "CN"

    def test_cn_bare(self) -> None:
        assert finbot._infer_market_from_ticker("002025") == "CN"

    def test_hk(self) -> None:
        assert finbot._infer_market_from_ticker("700.HK") == "HK"
        assert finbot._infer_market_from_ticker("09988.HK") == "HK"

    def test_us(self) -> None:
        assert finbot._infer_market_from_ticker("NVDA") == "US"
        assert finbot._infer_market_from_ticker("TSLA") == "US"

    def test_default_fallback(self) -> None:
        assert finbot._infer_market_from_ticker("unknown_format") == "CN"


class TestCoerceValuationFrameWithMarketTruth:
    """Tests for _coerce_valuation_frame() market_truth integration."""

    def test_without_market_truth(self) -> None:
        result = finbot._coerce_valuation_frame({
            "current_view": "test view",
            "base_case": "base",
        })
        assert result["current_view"] == "test view"
        assert "market_truth" not in result

    def test_with_market_truth(self) -> None:
        mt = {"price": 38.5, "pe_ttm": 42.1, "market_cap": 230.0}
        result = finbot._coerce_valuation_frame(
            {"current_view": "test view"},
            market_truth=mt,
        )
        assert result["market_truth"] == mt
        assert result["current_view"] == "test view"

    def test_empty_raw_returns_frame_with_market_truth(self) -> None:
        mt = {"price": 100.0}
        result = finbot._coerce_valuation_frame(None, market_truth=mt)
        assert result["market_truth"] == mt
        assert result["current_view"] == ""

    def test_none_market_truth_not_included(self) -> None:
        result = finbot._coerce_valuation_frame({"current_view": "test"}, market_truth=None)
        assert "market_truth" not in result
