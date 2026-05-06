from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.advisor.runtime import get_advisor_runtime, reset_advisor_runtime
from ops.run_openmind_live_crystal_evidence import run_live_crystal_evidence


def test_run_openmind_live_crystal_evidence_produces_nonzero_shadow_samples(tmp_path: Path) -> None:
    reset_advisor_runtime()
    runtime = get_advisor_runtime()
    memory_db = runtime.memory._db_path
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(
        json.dumps(
            [
                {
                    "account_id": "acct-test",
                    "thread_id": "thread-test",
                    "session_id": "sess-test",
                    "agent_id": "advisor",
                    "role_id": "planning",
                    "project_id": "prs",
                    "message": "要高质量，按 Codex 标准来。",
                },
                {
                    "account_id": "acct-test",
                    "thread_id": "thread-test",
                    "session_id": "sess-test",
                    "agent_id": "advisor",
                    "role_id": "planning",
                    "project_id": "prs",
                    "message": "质量不够高，还要提高到Codex。",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_live_crystal_evidence(
        memory_db=memory_db,
        cases_file=cases_file,
        output_root=tmp_path / "out",
        sample_size=5,
    )

    assert result["ok"] is True
    summary = result["summary"]
    assert summary["after"]["user_correction_records"] >= 1
    assert summary["after"]["records_scanned"] >= 1
    assert summary["after"]["active_crystal_count"] >= 1
    payload = json.loads(Path(result["artifacts"][0]).read_text(encoding="utf-8"))
    assert payload["delta"]["active_crystal_count"] >= 1
