from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.evomap.knowledge.extractors.chat_followup import JobData, is_execution_only


def _write_job(
    root: Path,
    job_id: str,
    *,
    answer_state: str,
    authoritative_name: str = "answer.md",
    answer_text: str = "authoritative answer\n",
) -> Path:
    job_dir = root / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "request.json").write_text(
        json.dumps({"kind": "chatgpt_web.ask", "input": {"question": "How should we design this?"}}),
        encoding="utf-8",
    )
    (job_dir / authoritative_name).write_text(answer_text, encoding="utf-8")
    (job_dir / "result.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "answer_chars": len(answer_text),
                "completion_contract": {
                    "kind": "chatgpt_web.ask",
                    "answer_state": answer_state,
                    "finality_reason": "completed" if answer_state == "final" else "completed_under_min_chars",
                    "authoritative_answer_path": f"jobs/{job_id}/{authoritative_name}",
                    "answer_provenance": {"contract_class": "research"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return job_dir


def test_execution_only_filters_completed_but_non_final_research(tmp_path: Path) -> None:
    job_dir = _write_job(tmp_path, "job-1", answer_state="provisional")
    job = JobData(str(job_dir))

    assert job.answer_state == "provisional"
    assert job.is_authoritative_final is False
    assert is_execution_only(job) is True


def test_jobdata_reads_authoritative_answer_path(tmp_path: Path) -> None:
    long_answer = ("final answer from authoritative path " * 5).strip() + "\n"
    job_dir = _write_job(
        tmp_path,
        "job-2",
        answer_state="final",
        authoritative_name="answer.txt",
        answer_text=long_answer,
    )
    job = JobData(str(job_dir))

    assert job.is_authoritative_final is True
    assert is_execution_only(job) is False
    assert job.authoritative_answer_path == "jobs/job-2/answer.txt"
    assert "final answer from authoritative path" in job.answer
