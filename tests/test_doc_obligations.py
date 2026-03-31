from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from chatgptrest.repo_cognition.obligations import compute_change_obligations, validate_obligations


def _load_script():
    path = Path("scripts/check_doc_obligations.py").resolve()
    spec = importlib.util.spec_from_file_location("chatgptrest_check_doc_obligations_test", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_compute_change_obligations_marks_missing_updates() -> None:
    obligations = compute_change_obligations(["chatgptrest/mcp/agent_mcp.py"])

    obligation = next(item for item in obligations if item["pattern"] == "chatgptrest/mcp/")
    assert obligation["must_update"] == ["AGENTS.md"]
    assert obligation["missing_updates"] == ["AGENTS.md"]
    assert "tests/test_agent_mcp.py" in obligation["baseline_tests"]


def test_validate_obligations_fails_when_doc_not_updated() -> None:
    obligations = compute_change_obligations(["chatgptrest/mcp/agent_mcp.py"])

    validation = validate_obligations(obligations)

    assert validation["ok"] is False
    assert validation["required_docs"] == ["AGENTS.md"]
    assert validation["missing_updates"] == ["AGENTS.md"]


def test_check_doc_obligations_json_exits_nonzero_for_missing_updates(capsys) -> None:
    mod = _load_script()

    rc = mod.main(["--changed-files", "chatgptrest/mcp/agent_mcp.py", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["validation"]["missing_updates"] == ["AGENTS.md"]
