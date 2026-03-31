"""Scoped auth-hardening and secret-source gate."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.eval.public_auth_trace_gate import DEFAULT_ENV_FILE as DEFAULT_AUTH_ENV_FILE


DEFAULT_API_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_ENV_FILE = DEFAULT_AUTH_ENV_FILE
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE16_REPORT = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase16_public_auth_trace_gate_20260322" / "report_v1.json"
REQUIRED_CLIENTS = ("chatgptrest-mcp", "chatgptrestctl", "openclaw-advisor")


@dataclass
class AuthHardeningCheck:
    name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    mismatches: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "details": dict(self.details),
            "mismatches": dict(self.mismatches),
        }


@dataclass
class AuthHardeningGateReport:
    base_url: str
    env_file: str
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[AuthHardeningCheck]
    scope_boundary: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "env_file": self.env_file,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": list(self.scope_boundary),
        }


def run_auth_hardening_secret_source_gate(
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    env_file: Path = DEFAULT_ENV_FILE,
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> AuthHardeningGateReport:
    health = _get_health(base_url=base_url)
    env_values = _load_env_values(env_file)
    phase16 = _read_json(PHASE16_REPORT)
    secret_values = [
        value
        for key, value in env_values.items()
        if key in {"OPENMIND_API_KEY", "CHATGPTREST_API_TOKEN"} and value
    ]
    leaks = _find_secret_leaks(repo_root=repo_root, secret_values=secret_values)
    checks = [
        _build_auth_health_check(health),
        _build_secret_source_check(env_file=env_file, env_values=env_values, repo_root=repo_root),
        _build_allowlist_check(env_values=env_values),
        _build_repo_leak_check(leaks=leaks),
        _build_phase16_check(phase16),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return AuthHardeningGateReport(
        base_url=str(base_url).rstrip("/"),
        env_file=str(env_file),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        scope_boundary=[
            "strict auth mode on the live advisor health surface",
            "secret source anchored in the local home config, outside the repo",
            "client-name allowlist locked without wildcard expansion",
            "tracked repository files scanned for literal secret leakage",
            "inherits live auth write proof from Phase 16",
            "not a full identity-hardening review",
        ],
    )


def render_auth_hardening_secret_source_gate_markdown(report: AuthHardeningGateReport) -> str:
    lines = [
        "# Auth Hardening Secret Source Gate Report",
        "",
        f"- base_url: {report.base_url}",
        f"- env_file: {report.env_file}",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for check in report.checks:
        details = ", ".join(f"{key}={value}" for key, value in check.details.items())
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in check.mismatches.items()
        )
        lines.append(
            "| {name} | {passed} | {details} | {mismatch} |".format(
                name=_escape_pipe(check.name),
                passed="yes" if check.passed else "no",
                details=_escape_pipe(details or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    lines.append("")
    lines.append("## Scope Boundary")
    lines.append("")
    for item in report.scope_boundary:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_auth_hardening_secret_source_gate_report(
    report: AuthHardeningGateReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_auth_hardening_secret_source_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_auth_health_check(health: dict[str, Any]) -> AuthHardeningCheck:
    auth = ((health.get("subsystems") or {}) if isinstance(health.get("subsystems"), dict) else {}).get("auth")
    auth = auth if isinstance(auth, dict) else {}
    details = {
        "http_status": int(health.get("status_code") or 0),
        "auth_mode": str(auth.get("mode") or ""),
        "key_set": bool(auth.get("key_set") or False),
    }
    expectations = {"http_status": 200, "auth_mode": "strict", "key_set": True}
    mismatches = {
        field_name: {"expected": expected, "actual": details[field_name]}
        for field_name, expected in expectations.items()
        if details[field_name] != expected
    }
    return AuthHardeningCheck(
        name="auth_health_surface",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_secret_source_check(*, env_file: Path, env_values: dict[str, str], repo_root: Path) -> AuthHardeningCheck:
    mode = stat.S_IMODE(env_file.stat().st_mode) if env_file.exists() else 0
    details = {
        "env_exists": env_file.exists(),
        "env_outside_repo": not _is_relative_to(env_file.resolve(), repo_root.resolve()),
        "has_openmind_api_key": bool(env_values.get("OPENMIND_API_KEY")),
        "has_chatgptrest_api_token": bool(env_values.get("CHATGPTREST_API_TOKEN")),
        "world_accessible": bool(mode & 0o007),
        "mode_octal": oct(mode),
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if not details["env_exists"]:
        mismatches["env_exists"] = {"expected": True, "actual": details["env_exists"]}
    if not details["env_outside_repo"]:
        mismatches["env_outside_repo"] = {"expected": True, "actual": details["env_outside_repo"]}
    if not (details["has_openmind_api_key"] or details["has_chatgptrest_api_token"]):
        mismatches["auth_secret_present"] = {"expected": True, "actual": False}
    if details["world_accessible"]:
        mismatches["world_accessible"] = {"expected": False, "actual": details["world_accessible"]}
    return AuthHardeningCheck(
        name="secret_source_local_env",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_allowlist_check(*, env_values: dict[str, str]) -> AuthHardeningCheck:
    raw = str(env_values.get("CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST") or "")
    entries = [item.strip() for item in raw.split(",") if item.strip()]
    details = {
        "allowlist": entries,
        "has_wildcard": "*" in entries,
        "required_clients_present": all(client in entries for client in REQUIRED_CLIENTS),
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if details["has_wildcard"]:
        mismatches["has_wildcard"] = {"expected": False, "actual": details["has_wildcard"]}
    if not details["required_clients_present"]:
        mismatches["required_clients_present"] = {"expected": True, "actual": details["required_clients_present"]}
    return AuthHardeningCheck(
        name="client_allowlist_locked",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_repo_leak_check(*, leaks: list[str]) -> AuthHardeningCheck:
    details = {"leak_count": len(leaks), "leak_paths": leaks[:10]}
    mismatches: dict[str, dict[str, Any]] = {}
    if leaks:
        mismatches["leak_count"] = {"expected": 0, "actual": len(leaks)}
    return AuthHardeningCheck(
        name="tracked_repo_secret_leak_scan",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_phase16_check(phase16: dict[str, Any]) -> AuthHardeningCheck:
    details = {
        "report": str(PHASE16_REPORT),
        "num_failed": int(phase16.get("num_failed") or 0),
        "num_checks": int(phase16.get("num_checks") or 0),
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if details["num_failed"] != 0:
        mismatches["num_failed"] = {"expected": 0, "actual": details["num_failed"]}
    return AuthHardeningCheck(
        name="phase16_public_auth_trace_clean",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _get_health(*, base_url: str) -> dict[str, Any]:
    request = urllib.request.Request(str(base_url).rstrip("/") + "/v2/advisor/health", method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8", errors="replace")
    return {"status_code": response.status, **(json.loads(text) if text else {})}


def _load_env_values(env_file: Path) -> dict[str, str]:
    values = {
        "OPENMIND_API_KEY": "",
        "CHATGPTREST_API_TOKEN": "",
        "CHATGPTREST_ENFORCE_CLIENT_NAME_ALLOWLIST": "",
    }
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key_n = key.strip()
            if key_n not in values or values[key_n]:
                continue
            values[key_n] = value.strip().strip('"').strip("'")
    for key in list(values):
        if not values[key]:
            values[key] = os.environ.get(key, "").strip()
    return values


def _find_secret_leaks(*, repo_root: Path, secret_values: list[str]) -> list[str]:
    cleaned_values = [value for value in secret_values if value]
    if not cleaned_values:
        return []
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    leaks: list[str] = []
    for raw_path in proc.stdout.split(b"\x00"):
        if not raw_path:
            continue
        rel_path = raw_path.decode("utf-8", errors="replace")
        path = repo_root / rel_path
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:1024]:
            continue
        text = data.decode("utf-8", errors="replace")
        if any(secret in text for secret in cleaned_values):
            leaks.append(rel_path)
    return leaks


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")
