#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.core.openmind_paths import resolve_evomap_knowledge_runtime_db_path
from ops.build_execution_experience_attention_manifest import build_manifest as build_attention_manifest
from ops.build_execution_experience_controller_action_plan import build_plan as build_controller_action_plan
from ops.build_execution_experience_controller_reply_packet import (
    build_packet as build_controller_reply_packet,
)
from ops.build_execution_experience_controller_rollup_manifest import (
    build_manifest as build_controller_rollup_manifest,
)
from ops.build_execution_experience_controller_update_note import build_note as build_controller_update_note
from ops.build_execution_experience_controller_packet import build_packet as build_controller_packet
from ops.build_execution_experience_followup_manifest import build_manifest as build_followup_manifest
from ops.build_execution_experience_governance_snapshot import build_snapshot as build_governance_snapshot
from ops.build_execution_experience_progress_delta import build_delta as build_progress_delta
from ops.build_execution_experience_review_reply_draft import build_draft as build_review_reply_draft
from ops.build_execution_experience_deferred_revisit_queue import build_queue as build_deferred_revisit_queue
from ops.build_execution_experience_rejected_archive_queue import build_queue as build_rejected_archive_queue
from ops.export_execution_experience_acceptance_pack import export_pack as export_acceptance_pack
from ops.build_execution_experience_revision_worklist import build_worklist as build_revision_worklist
from ops.build_execution_experience_review_decision_scaffold import build_scaffold as build_decision_scaffold
from ops.build_execution_experience_review_pack import build_review_pack
from ops.compose_execution_experience_review_decisions import compose, next_versioned_decision_name
from ops.export_execution_experience_governance_queues import export_queues as export_governance_queues
from ops.export_execution_experience_candidates import export_candidates
from ops.merge_execution_experience_review_outputs import materialize_reviewed_candidates, merge_review_outputs
from ops.report_execution_experience_review_backlog import report_backlog
from ops.render_execution_experience_review_brief import render_brief
from ops.validate_execution_experience_review_outputs import validate_review_outputs


DEFAULT_ACTIVITY_REVIEW_ROOT = REPO_ROOT / "artifacts" / "monitor" / "execution_activity_review_cycle"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "monitor" / "execution_experience_review_cycle"
REVIEWER_NAMES = ("gemini_no_mcp", "claudeminmax", "codex_auth_only")


def _new_cycle_dir(root: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = root / ts
    if not candidate.exists():
        return candidate
    idx = 1
    while True:
        candidate = root / f"{ts}_{idx:02d}"
        if not candidate.exists():
            return candidate
        idx += 1


def _execution_decision_file(snapshot_dir: Path) -> Path | None:
    candidates = sorted(snapshot_dir.glob("execution_review_decisions_v*.tsv"))
    if candidates:
        return candidates[-1]
    fallback = snapshot_dir / "execution_review_decisions.tsv"
    if fallback.exists():
        return fallback
    return None


def _experience_decision_file(snapshot_dir: Path) -> Path | None:
    candidates = sorted(snapshot_dir.glob("execution_experience_review_decisions_v*.tsv"))
    if candidates:
        return candidates[-1]
    fallback = snapshot_dir / "execution_experience_review_decisions.tsv"
    if fallback.exists():
        return fallback
    return None


def _latest_dir_with_file(root: Path, finder: Any, *, exclude: Path | None = None) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir() and path != exclude and finder(path)]
    candidates.sort(key=lambda path: path.name)
    return candidates[-1] if candidates else None


def _build_reviewer_manifest(snapshot_dir: Path, pack_path: Path) -> dict[str, Any]:
    review_root = snapshot_dir / "review_runs_cycle"
    review_root.mkdir(parents=True, exist_ok=True)
    reviewers: list[dict[str, str]] = []
    for name in REVIEWER_NAMES:
        output_path = review_root / f"{name}.json"
        reviewers.append(
            {
                "reviewer": name,
                "output_path": str(output_path),
                "instruction": (
                    f"Review execution experience pack {pack_path} and write JSON to {output_path}. "
                    "Return only review items for candidates in the pack."
                ),
            }
        )
    manifest = {
        "pack_path": str(pack_path),
        "review_output_dir": str(review_root),
        "reviewers": reviewers,
    }
    manifest_path = review_root / "reviewer_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"manifest_path": str(manifest_path), "review_output_dir": str(review_root), "reviewers": reviewers}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Expected JSON object at {path}")


def _validation_errors(
    summary: dict[str, Any],
    *,
    require_valid_reviews: bool,
    require_complete_reviews: bool,
) -> list[str]:
    errors: list[str] = []
    if require_valid_reviews and not summary.get("structurally_valid", False):
        errors.append(
            "review outputs failed structural validation"
            f" (unknown={summary.get('unknown_candidate_items', 0)},"
            f" invalid={summary.get('invalid_decision_items', 0)},"
            f" duplicate={summary.get('duplicate_candidate_items', 0)})"
        )
    if require_complete_reviews and not summary.get("complete", False):
        missing = summary.get("missing_reviewers") or []
        errors.append(f"review outputs incomplete (missing_reviewers={','.join(str(item) for item in missing)})")
    return errors


def _latest_progress_baseline_dir(root: Path, *, exclude: Path | None = None) -> Path | None:
    return _latest_dir_with_file(
        root,
        lambda path: (path / "governance_snapshot.json").exists() and (path / "controller_action_plan.json").exists(),
        exclude=exclude,
    )


def _maybe_build_progress_delta(
    *,
    output_dir: Path,
    output_root: Path,
    governance_snapshot: dict[str, Any],
    controller_action_plan: dict[str, Any],
) -> dict[str, Any] | None:
    previous_dir = _latest_progress_baseline_dir(output_root, exclude=output_dir)
    if previous_dir is None:
        return None
    previous_governance_snapshot = _load_json(previous_dir / "governance_snapshot.json")
    previous_governance_snapshot["output_path"] = str(previous_dir / "governance_snapshot.json")
    previous_controller_action_plan = _load_json(previous_dir / "controller_action_plan.json")
    previous_controller_action_plan["output_path"] = str(previous_dir / "controller_action_plan.json")
    return build_progress_delta(
        output_path=output_dir / "progress_delta.json",
        previous_governance_snapshot=previous_governance_snapshot,
        current_governance_snapshot=governance_snapshot,
        previous_controller_action_plan=previous_controller_action_plan,
        current_controller_action_plan=controller_action_plan,
    )


def run_cycle(
    *,
    db_path: str | Path,
    output_root: Path,
    activity_review_root: Path,
    decisions_path: Path | None,
    review_json_paths: list[Path],
    base_experience_decisions_path: Path | None,
    limit: int,
    require_valid_reviews: bool = False,
    require_complete_reviews: bool = False,
) -> dict[str, Any]:
    out = _new_cycle_dir(output_root)
    out.mkdir(parents=True, exist_ok=True)

    decision_source_dir = ""
    if decisions_path is None:
        source_dir = _latest_dir_with_file(activity_review_root, _execution_decision_file)
        if source_dir is None:
            raise FileNotFoundError(
                "No execution review decisions baseline found. Pass --decisions or produce execution_review_decisions_v1.tsv first."
            )
        decisions_path = _execution_decision_file(source_dir)
        decision_source_dir = str(source_dir)
    assert decisions_path is not None

    candidate_export = export_candidates(
        db_path=db_path,
        decisions_path=decisions_path,
        output_dir=out / "candidate_export",
    )
    candidates_json = Path(candidate_export["output_dir"]) / "experience_candidates.json"
    if base_experience_decisions_path is None:
        previous_dir = _latest_dir_with_file(output_root, _experience_decision_file, exclude=out)
        base_experience_decisions_path = _experience_decision_file(previous_dir) if previous_dir else None
    pack_result = build_review_pack(
        candidates_path=candidates_json,
        output_dir=out / "review_pack",
        limit=limit,
    )
    reviewer_manifest: dict[str, Any] = {}
    if pack_result["selected_candidates"] > 0:
        reviewer_manifest = _build_reviewer_manifest(out, Path(pack_result["pack_path"]))

    review_backlog = report_backlog(
        candidates_path=candidates_json,
        decisions_path=base_experience_decisions_path,
        reviewer_manifest_path=Path(reviewer_manifest["manifest_path"]) if reviewer_manifest else None,
    )
    review_backlog_path = out / "review_backlog_summary.json"
    _write_json(review_backlog_path, review_backlog)
    decision_scaffold = build_decision_scaffold(
        candidates_path=candidates_json,
        decisions_path=base_experience_decisions_path,
        reviewer_manifest_path=Path(reviewer_manifest["manifest_path"]) if reviewer_manifest else None,
        output_tsv=out / "review_decision_scaffold.tsv",
    )
    governance_queues = export_governance_queues(
        input_tsv=decision_scaffold["output_tsv"],
        output_dir=out / "governance_queues",
    )
    revision_worklist = build_revision_worklist(
        candidates_path=candidates_json,
        decisions_path=base_experience_decisions_path,
        output_tsv=out / "revision_worklist.tsv",
    )
    acceptance_pack = export_acceptance_pack(
        candidates_path=candidates_json,
        decisions_path=base_experience_decisions_path,
        output_dir=out / "accepted_pack",
    )
    deferred_revisit_queue = build_deferred_revisit_queue(
        candidates_path=candidates_json,
        decisions_path=base_experience_decisions_path,
        output_tsv=out / "deferred_revisit_queue.tsv",
    )
    rejected_archive_queue = build_rejected_archive_queue(
        candidates_path=candidates_json,
        decisions_path=base_experience_decisions_path,
        output_tsv=out / "rejected_archive_queue.tsv",
    )
    followup_manifest = build_followup_manifest(
        output_path=out / "followup_manifest.json",
        acceptance_pack=acceptance_pack,
        revision_worklist=revision_worklist,
        deferred_revisit_queue=deferred_revisit_queue,
        rejected_archive_queue=rejected_archive_queue,
    )
    governance_snapshot = build_governance_snapshot(
        output_path=out / "governance_snapshot.json",
        review_backlog=review_backlog,
        review_validation=None,
        governance_queues=governance_queues,
        followup_manifest=followup_manifest,
    )
    attention_manifest = build_attention_manifest(
        output_path=out / "attention_manifest.json",
        review_pack=pack_result,
        reviewer_manifest=reviewer_manifest,
        review_backlog=review_backlog,
        review_backlog_path=review_backlog_path,
        review_decision_scaffold_path=decision_scaffold["output_tsv"],
        review_validation=None,
        governance_queues=governance_queues,
        followup_manifest=followup_manifest,
    )
    review_brief = render_brief(
        output_path=out / "review_brief.md",
        governance_snapshot=governance_snapshot,
        attention_manifest=attention_manifest,
    )
    governance_snapshot["output_path"] = governance_snapshot["output_path"]
    review_reply_draft = build_review_reply_draft(
        output_path=out / "review_reply_draft.md",
        governance_snapshot=governance_snapshot,
        review_brief_path=review_brief["output_path"],
        attention_manifest_path=attention_manifest["output_path"],
    )
    controller_packet = build_controller_packet(
        output_path=out / "controller_packet.json",
        governance_snapshot=governance_snapshot,
        attention_manifest=attention_manifest,
        review_brief_path=review_brief["output_path"],
        review_reply_draft=review_reply_draft,
    )
    controller_action_plan = build_controller_action_plan(
        output_path=out / "controller_action_plan.json",
        controller_packet=controller_packet,
        attention_manifest=attention_manifest,
    )
    progress_delta = _maybe_build_progress_delta(
        output_dir=out,
        output_root=output_root,
        governance_snapshot=governance_snapshot,
        controller_action_plan=controller_action_plan,
    )
    controller_update_note = build_controller_update_note(
        output_path=out / "controller_update_note.md",
        controller_packet=controller_packet,
        controller_action_plan=controller_action_plan,
        progress_delta=progress_delta,
    )
    controller_rollup_manifest = build_controller_rollup_manifest(
        output_path=out / "controller_rollup_manifest.json",
        controller_packet=controller_packet,
        controller_action_plan=controller_action_plan,
        controller_update_note_path=controller_update_note["output_path"],
        progress_delta=progress_delta,
    )
    controller_reply_packet = build_controller_reply_packet(
        output_path=out / "controller_reply_packet.json",
        controller_rollup_manifest=controller_rollup_manifest,
        controller_action_plan=controller_action_plan,
        controller_update_note_path=controller_update_note["output_path"],
    )

    payload: dict[str, Any] = {
        "ok": True,
        "mode": "refresh_only",
        "decision_source_dir": decision_source_dir,
        "execution_decisions_path": str(decisions_path),
        "candidate_export": candidate_export,
        "review_pack": pack_result,
        "reviewer_manifest": reviewer_manifest,
        "review_backlog": review_backlog,
        "review_backlog_path": str(review_backlog_path),
        "review_decision_scaffold": decision_scaffold,
        "review_decision_scaffold_path": decision_scaffold["output_tsv"],
        "governance_queues": governance_queues,
        "governance_queue_summary_path": governance_queues["summary_path"],
        "revision_worklist": revision_worklist,
        "revision_worklist_path": revision_worklist["output_tsv"],
        "acceptance_pack": acceptance_pack,
        "acceptance_pack_manifest_path": acceptance_pack["manifest_path"],
        "deferred_revisit_queue": deferred_revisit_queue,
        "deferred_revisit_queue_path": deferred_revisit_queue["output_tsv"],
        "rejected_archive_queue": rejected_archive_queue,
        "rejected_archive_queue_path": rejected_archive_queue["output_tsv"],
        "followup_manifest": followup_manifest,
        "followup_manifest_path": followup_manifest["output_path"],
        "governance_snapshot": governance_snapshot,
        "governance_snapshot_path": governance_snapshot["output_path"],
        "attention_manifest": attention_manifest,
        "attention_manifest_path": attention_manifest["output_path"],
        "review_brief": review_brief,
        "review_brief_path": review_brief["output_path"],
        "review_reply_draft": review_reply_draft,
        "review_reply_draft_path": review_reply_draft["output_path"],
        "controller_packet": controller_packet,
        "controller_packet_path": controller_packet["output_path"],
        "controller_action_plan": controller_action_plan,
        "controller_action_plan_path": controller_action_plan["output_path"],
        "progress_delta": progress_delta,
        "progress_delta_path": progress_delta["output_path"] if progress_delta else "",
        "controller_update_note": controller_update_note,
        "controller_update_note_path": controller_update_note["output_path"],
        "controller_rollup_manifest": controller_rollup_manifest,
        "controller_rollup_manifest_path": controller_rollup_manifest["output_path"],
        "controller_reply_packet": controller_reply_packet,
        "controller_reply_packet_path": controller_reply_packet["output_path"],
    }
    if not review_json_paths:
        cycle_summary = out / "cycle_summary.json"
        _write_json(cycle_summary, payload)
        payload["cycle_summary_path"] = str(cycle_summary)
        return payload

    missing = [str(path) for path in review_json_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing review outputs: {missing}")

    review_validation = validate_review_outputs(
        candidates_path=candidates_json,
        review_json_paths=review_json_paths,
        reviewer_manifest_path=Path(reviewer_manifest["manifest_path"]) if reviewer_manifest else None,
    )
    review_validation_path = out / "review_output_validation_summary.json"
    _write_json(review_validation_path, review_validation)
    review_validation["review_output_validation_path"] = str(review_validation_path)
    governance_snapshot = build_governance_snapshot(
        output_path=out / "governance_snapshot.json",
        review_backlog=review_backlog,
        review_validation=review_validation,
        governance_queues=governance_queues,
        followup_manifest=followup_manifest,
    )
    attention_manifest = build_attention_manifest(
        output_path=out / "attention_manifest.json",
        review_pack=pack_result,
        reviewer_manifest=reviewer_manifest,
        review_backlog=review_backlog,
        review_backlog_path=review_backlog_path,
        review_decision_scaffold_path=decision_scaffold["output_tsv"],
        review_validation=review_validation,
        governance_queues=governance_queues,
        followup_manifest=followup_manifest,
    )
    review_brief = render_brief(
        output_path=out / "review_brief.md",
        governance_snapshot=governance_snapshot,
        attention_manifest=attention_manifest,
    )
    review_reply_draft = build_review_reply_draft(
        output_path=out / "review_reply_draft.md",
        governance_snapshot=governance_snapshot,
        review_brief_path=review_brief["output_path"],
        attention_manifest_path=attention_manifest["output_path"],
    )
    controller_packet = build_controller_packet(
        output_path=out / "controller_packet.json",
        governance_snapshot=governance_snapshot,
        attention_manifest=attention_manifest,
        review_brief_path=review_brief["output_path"],
        review_reply_draft=review_reply_draft,
    )
    controller_action_plan = build_controller_action_plan(
        output_path=out / "controller_action_plan.json",
        controller_packet=controller_packet,
        attention_manifest=attention_manifest,
    )
    progress_delta = _maybe_build_progress_delta(
        output_dir=out,
        output_root=output_root,
        governance_snapshot=governance_snapshot,
        controller_action_plan=controller_action_plan,
    )
    controller_update_note = build_controller_update_note(
        output_path=out / "controller_update_note.md",
        controller_packet=controller_packet,
        controller_action_plan=controller_action_plan,
        progress_delta=progress_delta,
    )
    controller_rollup_manifest = build_controller_rollup_manifest(
        output_path=out / "controller_rollup_manifest.json",
        controller_packet=controller_packet,
        controller_action_plan=controller_action_plan,
        controller_update_note_path=controller_update_note["output_path"],
        progress_delta=progress_delta,
    )
    controller_reply_packet = build_controller_reply_packet(
        output_path=out / "controller_reply_packet.json",
        controller_rollup_manifest=controller_rollup_manifest,
        controller_action_plan=controller_action_plan,
        controller_update_note_path=controller_update_note["output_path"],
    )
    validation_errors = _validation_errors(
        review_validation,
        require_valid_reviews=require_valid_reviews,
        require_complete_reviews=require_complete_reviews,
    )
    if validation_errors:
        payload.update(
            {
                "ok": False,
                "mode": "validation_failed",
                "review_output_validation": review_validation,
                "review_output_validation_path": str(review_validation_path),
                "governance_snapshot": governance_snapshot,
                "governance_snapshot_path": governance_snapshot["output_path"],
                "attention_manifest": attention_manifest,
                "attention_manifest_path": attention_manifest["output_path"],
                "review_brief": review_brief,
                "review_brief_path": review_brief["output_path"],
                "review_reply_draft": review_reply_draft,
                "review_reply_draft_path": review_reply_draft["output_path"],
                "controller_packet": controller_packet,
                "controller_packet_path": controller_packet["output_path"],
                "controller_action_plan": controller_action_plan,
                "controller_action_plan_path": controller_action_plan["output_path"],
                "progress_delta": progress_delta,
                "progress_delta_path": progress_delta["output_path"] if progress_delta else "",
                "controller_update_note": controller_update_note,
                "controller_update_note_path": controller_update_note["output_path"],
                "controller_rollup_manifest": controller_rollup_manifest,
                "controller_rollup_manifest_path": controller_rollup_manifest["output_path"],
                "controller_reply_packet": controller_reply_packet,
                "controller_reply_packet_path": controller_reply_packet["output_path"],
                "validation_errors": validation_errors,
            }
        )
        cycle_summary = out / "cycle_summary.json"
        _write_json(cycle_summary, payload)
        payload["cycle_summary_path"] = str(cycle_summary)
        raise RuntimeError("; ".join(validation_errors))

    delta_output = out / "execution_experience_review_decisions_delta_v1.tsv"
    merge_summary = merge_review_outputs(
        candidates_path=candidates_json,
        review_json_paths=review_json_paths,
        output_path=delta_output,
        reviewer_manifest_path=Path(reviewer_manifest["manifest_path"]) if reviewer_manifest else None,
    )

    full_output = out / next_versioned_decision_name(base_experience_decisions_path)
    compose_summary = compose(base_experience_decisions_path, delta_output, full_output)
    reviewed = materialize_reviewed_candidates(
        candidates_path=candidates_json,
        decisions_path=full_output,
        output_dir=out / "reviewed_candidates",
    )
    review_backlog = report_backlog(
        candidates_path=candidates_json,
        decisions_path=full_output,
        reviewer_manifest_path=Path(reviewer_manifest["manifest_path"]) if reviewer_manifest else None,
    )
    _write_json(review_backlog_path, review_backlog)
    decision_scaffold = build_decision_scaffold(
        candidates_path=candidates_json,
        decisions_path=full_output,
        reviewer_manifest_path=Path(reviewer_manifest["manifest_path"]) if reviewer_manifest else None,
        output_tsv=out / "review_decision_scaffold.tsv",
    )
    governance_queues = export_governance_queues(
        input_tsv=decision_scaffold["output_tsv"],
        output_dir=out / "governance_queues",
    )
    revision_worklist = build_revision_worklist(
        candidates_path=candidates_json,
        decisions_path=full_output,
        output_tsv=out / "revision_worklist.tsv",
    )
    acceptance_pack = export_acceptance_pack(
        candidates_path=candidates_json,
        decisions_path=full_output,
        output_dir=out / "accepted_pack",
    )
    deferred_revisit_queue = build_deferred_revisit_queue(
        candidates_path=candidates_json,
        decisions_path=full_output,
        output_tsv=out / "deferred_revisit_queue.tsv",
    )
    rejected_archive_queue = build_rejected_archive_queue(
        candidates_path=candidates_json,
        decisions_path=full_output,
        output_tsv=out / "rejected_archive_queue.tsv",
    )
    followup_manifest = build_followup_manifest(
        output_path=out / "followup_manifest.json",
        acceptance_pack=acceptance_pack,
        revision_worklist=revision_worklist,
        deferred_revisit_queue=deferred_revisit_queue,
        rejected_archive_queue=rejected_archive_queue,
    )
    governance_snapshot = build_governance_snapshot(
        output_path=out / "governance_snapshot.json",
        review_backlog=review_backlog,
        review_validation=review_validation,
        governance_queues=governance_queues,
        followup_manifest=followup_manifest,
    )
    attention_manifest = build_attention_manifest(
        output_path=out / "attention_manifest.json",
        review_pack=pack_result,
        reviewer_manifest=reviewer_manifest,
        review_backlog=review_backlog,
        review_backlog_path=review_backlog_path,
        review_decision_scaffold_path=decision_scaffold["output_tsv"],
        review_validation=review_validation,
        governance_queues=governance_queues,
        followup_manifest=followup_manifest,
    )
    review_brief = render_brief(
        output_path=out / "review_brief.md",
        governance_snapshot=governance_snapshot,
        attention_manifest=attention_manifest,
    )
    review_reply_draft = build_review_reply_draft(
        output_path=out / "review_reply_draft.md",
        governance_snapshot=governance_snapshot,
        review_brief_path=review_brief["output_path"],
        attention_manifest_path=attention_manifest["output_path"],
    )
    controller_packet = build_controller_packet(
        output_path=out / "controller_packet.json",
        governance_snapshot=governance_snapshot,
        attention_manifest=attention_manifest,
        review_brief_path=review_brief["output_path"],
        review_reply_draft=review_reply_draft,
    )
    controller_action_plan = build_controller_action_plan(
        output_path=out / "controller_action_plan.json",
        controller_packet=controller_packet,
        attention_manifest=attention_manifest,
    )
    progress_delta = _maybe_build_progress_delta(
        output_dir=out,
        output_root=output_root,
        governance_snapshot=governance_snapshot,
        controller_action_plan=controller_action_plan,
    )
    controller_update_note = build_controller_update_note(
        output_path=out / "controller_update_note.md",
        controller_packet=controller_packet,
        controller_action_plan=controller_action_plan,
        progress_delta=progress_delta,
    )
    controller_rollup_manifest = build_controller_rollup_manifest(
        output_path=out / "controller_rollup_manifest.json",
        controller_packet=controller_packet,
        controller_action_plan=controller_action_plan,
        controller_update_note_path=controller_update_note["output_path"],
        progress_delta=progress_delta,
    )
    controller_reply_packet = build_controller_reply_packet(
        output_path=out / "controller_reply_packet.json",
        controller_rollup_manifest=controller_rollup_manifest,
        controller_action_plan=controller_action_plan,
        controller_update_note_path=controller_update_note["output_path"],
    )

    payload.update(
        {
            "mode": "refresh_merge_only",
            "delta_output": str(delta_output),
            "review_output_validation": review_validation,
            "review_output_validation_path": str(review_validation_path),
            "merge_summary": merge_summary,
            "base_experience_decisions_path": str(base_experience_decisions_path) if base_experience_decisions_path else "",
            "full_output": str(full_output),
            "compose_summary": compose_summary,
            "reviewed_candidates": reviewed,
            "review_backlog": review_backlog,
            "review_decision_scaffold": decision_scaffold,
            "review_decision_scaffold_path": decision_scaffold["output_tsv"],
            "governance_queues": governance_queues,
            "governance_queue_summary_path": governance_queues["summary_path"],
            "revision_worklist": revision_worklist,
            "revision_worklist_path": revision_worklist["output_tsv"],
            "acceptance_pack": acceptance_pack,
            "acceptance_pack_manifest_path": acceptance_pack["manifest_path"],
            "deferred_revisit_queue": deferred_revisit_queue,
            "deferred_revisit_queue_path": deferred_revisit_queue["output_tsv"],
            "rejected_archive_queue": rejected_archive_queue,
            "rejected_archive_queue_path": rejected_archive_queue["output_tsv"],
            "followup_manifest": followup_manifest,
            "followup_manifest_path": followup_manifest["output_path"],
            "governance_snapshot": governance_snapshot,
            "governance_snapshot_path": governance_snapshot["output_path"],
            "attention_manifest": attention_manifest,
            "attention_manifest_path": attention_manifest["output_path"],
            "review_brief": review_brief,
            "review_brief_path": review_brief["output_path"],
            "review_reply_draft": review_reply_draft,
            "review_reply_draft_path": review_reply_draft["output_path"],
            "controller_packet": controller_packet,
            "controller_packet_path": controller_packet["output_path"],
            "controller_action_plan": controller_action_plan,
            "controller_action_plan_path": controller_action_plan["output_path"],
            "progress_delta": progress_delta,
            "progress_delta_path": progress_delta["output_path"] if progress_delta else "",
            "controller_update_note": controller_update_note,
            "controller_update_note_path": controller_update_note["output_path"],
            "controller_rollup_manifest": controller_rollup_manifest,
            "controller_rollup_manifest_path": controller_rollup_manifest["output_path"],
            "controller_reply_packet": controller_reply_packet,
            "controller_reply_packet_path": controller_reply_packet["output_path"],
        }
    )
    cycle_summary = out / "cycle_summary.json"
    _write_json(cycle_summary, payload)
    payload["cycle_summary_path"] = str(cycle_summary)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one execution experience review maintenance cycle.")
    parser.add_argument("--db", default=resolve_evomap_knowledge_runtime_db_path())
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--activity-review-root", default=str(DEFAULT_ACTIVITY_REVIEW_ROOT))
    parser.add_argument("--decisions", default="", help="Execution review decisions TSV that gates candidate export.")
    parser.add_argument("--review-json", action="append", default=[], help="Reviewer JSON outputs. Repeat for multiple files.")
    parser.add_argument("--base-experience-decisions", default="", help="Optional full baseline execution experience review TSV.")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--require-valid-reviews", action="store_true")
    parser.add_argument("--require-complete-reviews", action="store_true")
    args = parser.parse_args()

    payload = run_cycle(
        db_path=args.db,
        output_root=Path(args.output_root),
        activity_review_root=Path(args.activity_review_root),
        decisions_path=Path(args.decisions) if args.decisions else None,
        review_json_paths=[Path(path) for path in args.review_json],
        base_experience_decisions_path=Path(args.base_experience_decisions) if args.base_experience_decisions else None,
        limit=args.limit,
        require_valid_reviews=args.require_valid_reviews,
        require_complete_reviews=args.require_complete_reviews,
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
