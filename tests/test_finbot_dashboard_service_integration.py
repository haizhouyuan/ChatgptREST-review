from __future__ import annotations

from pathlib import Path

from chatgptrest import finbot
from chatgptrest.core.config import load_config
from chatgptrest.dashboard.service import DashboardService
import chatgptrest.dashboard.service as dashboard_service_mod


def _stub_finbot_generation(monkeypatch) -> None:
    class _StubFinbotDashboardService:
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
                        "detail_href": "/v2/dashboard/investor/sources/tsmc-ir",
                    }
                ],
                "kols": [],
                "planning_doc_reader_href": "/v2/dashboard/reader?path=/allowed/planning.md",
                "planning_doc_path": "/allowed/planning.md",
            }

        def investor_theme_detail(self, theme_slug: str) -> dict[str, object]:
            assert theme_slug == "silicon_photonics"
            return {
                "theme": {
                    "theme_slug": "silicon_photonics",
                    "title": "硅光 / CPO",
                    "recommended_posture": "watch_with_prepare_candidate",
                    "best_expression": "中际旭创",
                },
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

    monkeypatch.setattr(finbot, "DashboardService", _StubFinbotDashboardService)
    monkeypatch.setattr(
        finbot,
        "_run_kol_suite",
        lambda **_: {"ok": True, "suite_slug": "finbot_candidate_tsmc_cpo", "consensus_topics": 2},
    )
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
                            "exact_quote": "Packaging capacity remains tight as advanced AI demand stays elevated.",
                            "supporting_sources": [
                                {
                                    "source_id": "tsmc-ir",
                                    "name": "TSMC IR",
                                    "detail_href": "/v2/dashboard/investor/sources/tsmc-ir",
                                    "contribution_role": "anchor",
                                    "excerpt": "Packaging capacity remains tight as advanced AI demand stays elevated.",
                                }
                            ],
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
                        {
                            "rank": 1,
                            "expression": "中际旭创",
                            "why_best": "最接近中国可行动表达",
                            "why_not_best": "",
                            "readiness": "prepare",
                            "valuation_anchor": "兑现先于重估",
                            "scenario_base": "模块主线",
                            "scenario_bull": "CPO 提前验证",
                            "scenario_bear": "ASP 回落",
                        },
                        {
                            "rank": 2,
                            "expression": "Broadcom",
                            "why_best": "海外平台",
                            "why_not_best": "不适合作为中国表达",
                            "readiness": "watch",
                        },
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


def _write_finbot_artifacts(tmp_path: Path, monkeypatch) -> None:
    _stub_finbot_generation(monkeypatch)
    result = finbot.opportunity_deepen(root=tmp_path, force=True)
    assert result["ok"] is True
    assert result["created"] is True

    brief_item = finbot.InboxItem(
        item_id="finbot-brief-candidate-tsmc-cpo",
        created_at=1.0,
        title="Finbot deepening brief · TSMC CPO packaging capacity ramp",
        summary="candidate_tsmc_cpo → deepen | class=frontier | TSMC confirms dedicated CPO capacity lane",
        category="deepening_brief",
        severity="accent",
        source="finagent.theme_radar",
        action_hint="Use this brief to decide whether to open a deeper research pass or attach the candidate to an existing theme.",
        payload={
            "logical_key": "candidate_tsmc_cpo",
            "candidate_id": "candidate_tsmc_cpo",
            "thesis_name": "TSMC CPO packaging capacity ramp",
            "route": "opportunity",
            "residual_class": "frontier",
            "note": "CoWoS 专线扩产可能成为新的 CPO 配套瓶颈。",
            "next_action": "deepen_now",
            "next_proving_milestone": "TSMC confirms dedicated CPO capacity lane",
            "ranking_score": 0.72,
            "suggested_sources": ["TSMC IR"],
            "related_themes": [
                {
                    "theme_slug": "silicon_photonics",
                    "title": "硅光 / CPO",
                    "detail_href": "/v2/dashboard/investor/themes/silicon_photonics",
                    "best_expression": "中际旭创",
                    "related_sources": ["TSMC IR"],
                }
            ],
            "research_questions": ["Which tracked theme should absorb this candidate first?"],
        },
    )
    finbot.write_inbox_item(brief_item, root=tmp_path)


def test_dashboard_service_reads_real_finbot_artifacts(tmp_path: Path, monkeypatch) -> None:
    _write_finbot_artifacts(tmp_path, monkeypatch)

    monkeypatch.setattr(dashboard_service_mod, "FINBOT_ARTIFACT_ROOT_CANDIDATES", (tmp_path,))
    monkeypatch.setattr(
        DashboardService,
        "_ensure_ready",
        lambda self: {"refreshed_at": 0.0, "refresh_status": "ready", "root_count": 1, "source_summary": {}},
    )

    spec_path = tmp_path / "virtual" / "2026-03-16_silicon_photonics_sentinel_v1.yaml"
    monkeypatch.setattr(DashboardService, "_theme_spec_paths", lambda self: [spec_path])
    monkeypatch.setattr(
        DashboardService,
        "_load_theme_spec",
        lambda self, path: {
            "theme": {
                "title": "硅光 / CPO",
                "investor_question": "当前最值得准备的表达是什么？",
                "thesis_statement": "核心和 option 要拆开。",
                "why_now": "1.6T 开始兑现。",
                "why_mispriced": "市场把 core 和 option 混着定价。",
                "current_posture": "watch_only",
            },
            "sentinel": [
                {"grammar_key": "cpo", "bucket_role": "core", "entity_role": "tracked"},
                {"grammar_key": "tsmc", "bucket_role": "option", "entity_role": "tracked"},
            ],
        },
    )
    monkeypatch.setattr(
        DashboardService,
        "_planning_snapshot",
        lambda self: {
            "planning_rows": [
                {
                    "KOL / 源": "TSMC IR",
                    "主题": "硅光 / CPO",
                    "核心逻辑": "CPO 不是只看芯片，真正瓶颈可能在 TSMC 封装产能与 hyperscaler 商业部署。",
                    "标的 / 表达": "TSMC、中际旭创",
                    "优先级": "P0",
                    "为什么选": "frontier opportunity 正在形成。",
                }
            ]
        },
    )
    monkeypatch.setattr(
        DashboardService,
        "_theme_radar_snapshot",
        lambda self: {
            "items": [
                {
                    "candidate_id": "candidate_tsmc_cpo",
                    "thesis_name": "TSMC CPO packaging capacity ramp",
                    "route": "opportunity",
                    "residual_class": "frontier",
                    "ranking_score": 0.72,
                    "note": "CoWoS 专线扩产可能成为新的 CPO 配套瓶颈。",
                    "next_action": "deepen_now",
                    "next_proving_milestone": "TSMC confirms dedicated CPO capacity lane",
                }
            ]
        },
    )
    monkeypatch.setattr(
        DashboardService,
        "_source_board_snapshot",
        lambda self: {
            "items": [
                    {
                        "source_id": "tsmc-ir",
                        "name": "TSMC IR",
                        "source_type": "official_disclosure",
                        "source_trust_tier": "anchor",
                    "source_priority_label": "watch",
                    "track_record_label": "emerging",
                    "primaryness": "first_hand",
                    "accepted_route_count": 10,
                    "validated_case_count": 2,
                    "claim_count": 5,
                    "latest_viewpoint_summary": "CoWoS / CPO capacity remains tight.",
                    "effective_operator_feedback_score": 0.0,
                }
            ]
        },
    )

    service = DashboardService(load_config())

    snapshot = service.investor_snapshot()
    assert snapshot["summary"]["theme_count"] == 1
    assert snapshot["summary"]["opportunity_count"] == 1
    assert snapshot["summary"]["research_package_count"] == 1
    assert snapshot["themes"][0]["related_opportunities"][0]["candidate_id"] == "candidate_tsmc_cpo"
    assert snapshot["opportunities"][0]["research_package"]["best_expression_today"] == "中际旭创"
    assert snapshot["opportunities"][0]["brief_next_action"] == "deepen_now"

    theme_detail = service.investor_theme_detail("silicon_photonics")
    assert theme_detail["theme"]["best_expression"].startswith("中际旭创")
    assert theme_detail["theme"]["related_opportunities"][0]["candidate_id"] == "candidate_tsmc_cpo"

    opportunity_detail = service.investor_opportunity_detail("candidate_tsmc_cpo")
    assert opportunity_detail["research_package"]["decision_card"]["best_expression_today"] == "中际旭创"
    assert opportunity_detail["research_package"]["citation_register"][0]["source_name"] == "TSMC IR"
    assert opportunity_detail["research_package"]["claim_support_map"]
    assert opportunity_detail["research_package"]["claim_evidence_bindings"]["bindings"][0]["source_name"] == "TSMC IR"
    assert opportunity_detail["research_package"]["policy_result"]["missing_evidence"] == []
    assert opportunity_detail["research_package"]["counterevidence_packets"]["packets"][0]["stance"] == "weaken"
    assert opportunity_detail["research_package"]["peer_snapshot"]["candidate_id"] == "candidate_tsmc_cpo"
    assert opportunity_detail["research_package"]["transcript_packet"]["provider"] == "disabled"
    assert opportunity_detail["research_package"]["primary_data_packet"]["promotion_enrichment"]["promotion_recommendation"] == "no_primary_data"
    assert opportunity_detail["related_sources"][0]["name"] == "TSMC IR"

    source_detail = service.investor_source_detail("tsmc-ir")
    assert source_detail["source"]["name"] == "TSMC IR"
    assert source_detail["source"]["supported_claim_count"] >= 1
    assert source_detail["source"]["score_history"]
    assert source_detail["source"]["support_history"][0]["candidate_id"] == "candidate_tsmc_cpo"
