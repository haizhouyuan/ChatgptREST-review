from __future__ import annotations

from pathlib import Path

import chatgptrest.eval.auth_hardening_secret_source_gate as mod


def test_run_auth_hardening_secret_source_gate_passes_with_clean_inputs(tmp_path: Path, monkeypatch) -> None:
    env_dir = tmp_path / "homecfg"
    env_dir.mkdir()
    env_file = env_dir / "chatgptrest.env"
    env_file.write_text(
        "\n".join(
            [
                "OPENMIND_API_KEY=test-openmind-token",
                "CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST=chatgptrest-mcp,chatgptrestctl,openclaw-advisor",
            ]
        ),
        encoding="utf-8",
    )
    env_file.chmod(0o640)
    phase16 = tmp_path / "phase16.json"
    phase16.write_text('{"num_failed":0,"num_checks":4}', encoding="utf-8")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(mod, "PHASE16_REPORT", phase16)
    monkeypatch.setattr(mod, "_get_health", lambda **kwargs: {"status_code": 200, "subsystems": {"auth": {"mode": "strict", "key_set": True}}})
    monkeypatch.setattr(mod, "_find_secret_leaks", lambda **kwargs: [])

    report = mod.run_auth_hardening_secret_source_gate(
        base_url="http://127.0.0.1:18711",
        env_file=env_file,
        repo_root=repo_root,
    )

    assert report.num_checks == 5
    assert report.num_failed == 0


def test_tracked_repo_secret_leak_check_fails_when_paths_present() -> None:
    check = mod._build_repo_leak_check(leaks=["docs/bad.txt"])

    assert not check.passed
    assert "leak_count" in check.mismatches


def test_auth_hardening_secret_source_report_writer_emits_json_and_markdown(tmp_path: Path) -> None:
    report = mod.AuthHardeningGateReport(
        base_url="http://127.0.0.1:18711",
        env_file=str(tmp_path / "chatgptrest.env"),
        num_checks=1,
        num_passed=1,
        num_failed=0,
        checks=[mod.AuthHardeningCheck(name="auth_health_surface", passed=True, details={"auth_mode": "strict"})],
        scope_boundary=["strict auth on scoped surface"],
    )

    json_path, md_path = mod.write_auth_hardening_secret_source_gate_report(report, out_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert "Auth Hardening Secret Source Gate Report" in md_path.read_text(encoding="utf-8")
