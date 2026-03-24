from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "ops" / "codex_sre_analyze_incident.py"
    spec = importlib.util.spec_from_file_location("chatgptrest_ops_codex_sre_analyze_incident", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_prompt_includes_issues_registry_snapshot(tmp_path: Path):
    mod = _load_module()

    inc_dir = tmp_path / "incident"
    (inc_dir / "snapshots").mkdir(parents=True, exist_ok=True)
    (inc_dir / "manifest.json").write_text('{"incident_id":"inc-1"}', encoding="utf-8")
    (inc_dir / "summary.md").write_text("hello", encoding="utf-8")
    (inc_dir / "snapshots" / "issues_registry.yaml").write_text("ISSUE-TEST", encoding="utf-8")

    prompt = mod._build_prompt(inc_dir)  # noqa: SLF001
    assert "snapshots/issues_registry.yaml" in prompt
    assert "ISSUE-TEST" in prompt


def test_build_prompt_includes_global_memory_when_provided(tmp_path: Path):
    mod = _load_module()

    inc_dir = tmp_path / "incident"
    (inc_dir / "snapshots").mkdir(parents=True, exist_ok=True)
    (inc_dir / "manifest.json").write_text('{"incident_id":"inc-1"}', encoding="utf-8")
    (inc_dir / "summary.md").write_text("hello", encoding="utf-8")

    global_md = tmp_path / "global_memory.md"
    global_md.write_text("GLOBAL-MEMORY", encoding="utf-8")

    prompt = mod._build_prompt(inc_dir, global_memory_md=global_md)  # noqa: SLF001
    assert "global_memory.md" in prompt
    assert "GLOBAL-MEMORY" in prompt
