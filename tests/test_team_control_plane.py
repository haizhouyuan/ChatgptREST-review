from __future__ import annotations

from chatgptrest.kernel.cc_executor import CcResult, CcTask
from chatgptrest.kernel.team_catalog import load_team_catalog
from chatgptrest.kernel.team_control_plane import TeamControlPlane


def test_catalog_loads_default_roles_and_topologies() -> None:
    bundle = load_team_catalog()

    assert "scout" in bundle.roles
    assert "review_triad" in bundle.topologies
    assert "writer_review" in bundle.gates

    topology = bundle.recommend_topology("architecture_review")
    assert topology is not None
    assert topology.topology_id == "review_triad"


def test_control_plane_creates_and_resolves_run_with_checkpoint() -> None:
    plane = TeamControlPlane(db_path=":memory:")
    spec, topology = plane.resolve_team_spec(topology_id="implementation_duo", task_type="bug_fix")
    assert spec is not None
    assert topology is not None

    task = CcTask(task_type="bug_fix", description="Fix the failing contract", trace_id="tr_tc")
    plane.create_run(
        team_run_id="trun_tc1",
        team_spec=spec,
        topology_id=topology.topology_id,
        task=task,
        repo="ChatgptREST",
    )

    scout_result = CcResult(
        ok=True,
        agent="native",
        task_type="bug_fix",
        output="scout evidence",
        elapsed_seconds=1.0,
        quality_score=0.8,
        trace_id="tr_tc:scout",
    )
    implementer_result = CcResult(
        ok=True,
        agent="native",
        task_type="bug_fix",
        output="implemented fix",
        elapsed_seconds=2.0,
        quality_score=0.9,
        trace_id="tr_tc:implementer",
    )
    plane.mark_role_started("trun_tc1", "scout", task_trace_id="tr_tc:scout")
    plane.mark_role_completed("trun_tc1", "scout", scout_result)
    plane.mark_role_started("trun_tc1", "implementer", task_trace_id="tr_tc:implementer")
    plane.mark_role_completed("trun_tc1", "implementer", implementer_result)

    final_result = CcResult(
        ok=True,
        agent="native-team",
        task_type="bug_fix",
        output="final integrated output",
        elapsed_seconds=3.0,
        quality_score=0.85,
        trace_id="tr_tc",
    )
    checkpoints = plane.finalize_run(
        team_run_id="trun_tc1",
        team_spec=spec,
        final_result=final_result,
        role_outcomes={
            "scout": {"ok": True, "quality_score": 0.8, "elapsed_seconds": 1.0, "error": ""},
            "implementer": {"ok": True, "quality_score": 0.9, "elapsed_seconds": 2.0, "error": ""},
        },
    )

    assert len(checkpoints) == 1
    assert checkpoints[0].gate_id == "writer_review"

    run = plane.get_run("trun_tc1")
    assert run is not None
    assert run["status"] == "needs_review"
    assert "writer_review" in run["digest"]
    assert len(run["roles"]) == 2

    resolved = plane.approve_checkpoint(checkpoints[0].checkpoint_id, actor="tester", reason="manual review complete")
    assert resolved is not None
    assert resolved["status"] == "approved"

    run_after = plane.get_run("trun_tc1")
    assert run_after is not None
    assert run_after["status"] == "completed"


def test_control_plane_keeps_run_open_until_all_checkpoints_resolved() -> None:
    plane = TeamControlPlane(db_path=":memory:")
    team = plane.catalog.build_team_spec("implementation_duo")
    team.metadata["gate_ids"] = ["writer_review", "low_quality"]

    task = CcTask(task_type="bug_fix", description="Fix the failing contract", trace_id="tr_multi")
    plane.create_run(
        team_run_id="trun_multi",
        team_spec=team,
        topology_id="implementation_duo",
        task=task,
        repo="ChatgptREST",
    )

    checkpoints = plane.finalize_run(
        team_run_id="trun_multi",
        team_spec=team,
        final_result=CcResult(
            ok=True,
            agent="native-team",
            task_type="bug_fix",
            output="final integrated output",
            elapsed_seconds=3.0,
            quality_score=0.5,
            trace_id="tr_multi",
        ),
        role_outcomes={
            "scout": {"ok": True, "quality_score": 0.8, "elapsed_seconds": 1.0, "error": ""},
            "implementer": {"ok": True, "quality_score": 0.9, "elapsed_seconds": 2.0, "error": ""},
        },
    )

    assert len(checkpoints) == 2
    first = plane.approve_checkpoint(checkpoints[0].checkpoint_id, actor="tester", reason="first approved")
    assert first is not None
    run_mid = plane.get_run("trun_multi")
    assert run_mid is not None
    assert run_mid["status"] == "needs_review"

    second = plane.approve_checkpoint(checkpoints[1].checkpoint_id, actor="tester", reason="second approved")
    assert second is not None
    run_after = plane.get_run("trun_multi")
    assert run_after is not None
    assert run_after["status"] == "completed"


def test_control_plane_rejected_checkpoint_marks_run_rejected() -> None:
    plane = TeamControlPlane(db_path=":memory:")
    team = plane.catalog.build_team_spec("implementation_duo")
    team.metadata["gate_ids"] = ["writer_review"]

    task = CcTask(task_type="bug_fix", description="Fix the failing contract", trace_id="tr_reject")
    plane.create_run(
        team_run_id="trun_reject",
        team_spec=team,
        topology_id="implementation_duo",
        task=task,
        repo="ChatgptREST",
    )

    checkpoints = plane.finalize_run(
        team_run_id="trun_reject",
        team_spec=team,
        final_result=CcResult(
            ok=True,
            agent="native-team",
            task_type="bug_fix",
            output="final integrated output",
            elapsed_seconds=3.0,
            quality_score=0.85,
            trace_id="tr_reject",
        ),
        role_outcomes={
            "scout": {"ok": True, "quality_score": 0.8, "elapsed_seconds": 1.0, "error": ""},
            "implementer": {"ok": True, "quality_score": 0.9, "elapsed_seconds": 2.0, "error": ""},
        },
    )

    assert len(checkpoints) == 1
    rejected = plane.reject_checkpoint(checkpoints[0].checkpoint_id, actor="tester", reason="blocked")
    assert rejected is not None
    run = plane.get_run("trun_reject")
    assert run is not None
    assert run["status"] == "rejected"


def test_resolve_team_spec_overlays_topology_metadata_for_explicit_team() -> None:
    plane = TeamControlPlane(db_path=":memory:")
    explicit = plane.catalog.build_team_spec("review_triad")
    explicit.metadata = {"custom_flag": "keep-me"}

    resolved, topology = plane.resolve_team_spec(
        team=explicit,
        topology_id="review_triad",
        task_type="architecture_review",
    )

    assert resolved is not None
    assert topology is not None
    assert topology.topology_id == "review_triad"
    assert [role.name for role in resolved.roles] == [role.name for role in explicit.roles]
    assert resolved.metadata["topology_id"] == "review_triad"
    assert resolved.metadata["execution_mode"] == "parallel"
    assert resolved.metadata["synthesis_role"] == "synthesizer"
    assert resolved.metadata["gate_ids"] == ["team_failure", "low_quality"]
    assert resolved.metadata["custom_flag"] == "keep-me"
