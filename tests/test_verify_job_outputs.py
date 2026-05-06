from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    path = Path("ops/verify_job_outputs.py").resolve()
    spec = importlib.util.spec_from_file_location("verify_job_outputs_test", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_verify_job_marks_completed_but_non_final_research(tmp_path: Path) -> None:
    mod = _load_module()
    job_dir = tmp_path / "artifacts" / "jobs" / "job-1"
    job_dir.mkdir(parents=True)
    (job_dir / "answer.txt").write_text("partial answer\n", encoding="utf-8")
    (job_dir / "result.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "phase": "wait",
                "completion_contract": {
                    "kind": "chatgpt_web.ask",
                    "answer_state": "provisional",
                    "finality_reason": "completed_under_min_chars",
                    "answer_chars": 15,
                    "min_chars_required": 1200,
                    "authoritative_answer_path": "jobs/job-1/answer.txt",
                    "answer_provenance": {"contract_class": "research"},
                    "export_available": False,
                    "widget_export_available": False,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (job_dir / "run_meta.json").write_text("{}", encoding="utf-8")
    (job_dir / "conversation.json").write_text("{}", encoding="utf-8")

    report = mod.verify_job(artifacts_dir=tmp_path / "artifacts", job_id="job-1", min_similarity=0.85)

    assert "completed_not_final" in report["warnings"]
    assert report["answer"]["path"].endswith("answer.txt")
    assert report["answer"]["answer_state"] == "provisional"
    assert report["answer"]["final_ready"] is False
    assert report["answer"]["authoritative_answer_path"] == "jobs/job-1/answer.txt"
