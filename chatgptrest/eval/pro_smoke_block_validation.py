"""Strict Pro smoke/trivial block validation."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from chatgptrest.api.app import create_app


ACTIVE_DOCS_FOR_PRO_BLOCK = (
    "AGENTS.md",
    "docs/contract_v1.md",
    "docs/runbook.md",
    "docs/client_projects_registry.md",
)
LEGACY_OVERRIDE_TOKENS = ("allow_trivial_pro_prompt", "allow_pro_smoke_test")


@dataclass
class ProSmokeBlockCheckResult:
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
class ProSmokeBlockValidationReport:
    num_checks: int
    num_passed: int
    num_failed: int
    results: list[ProSmokeBlockCheckResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "results": [item.to_dict() for item in self.results],
        }


def run_pro_smoke_block_validation() -> ProSmokeBlockValidationReport:
    with tempfile.TemporaryDirectory(prefix="phase14-pro-smoke-block-") as tmp_dir:
        client = _build_test_client(Path(tmp_dir))
        checks = [
            _check_chatgpt_pro_smoke_override_blocked(client),
            _check_chatgpt_pro_trivial_override_blocked(client),
            _check_gemini_pro_smoke_override_blocked(client),
            _check_active_docs_scrubbed(),
        ]

    num_passed = sum(1 for item in checks if item.passed)
    return ProSmokeBlockValidationReport(
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        results=checks,
    )


def render_pro_smoke_block_report_markdown(report: ProSmokeBlockValidationReport) -> str:
    lines = [
        "# Strict Pro Smoke Block Validation Report",
        "",
        f"- checks: {report.num_checks}",
        f"- passed: {report.num_passed}",
        f"- failed: {report.num_failed}",
        "",
        "| Check | Pass | Key Details | Mismatch |",
        "|---|---:|---|---|",
    ]
    for result in report.results:
        details = ", ".join(f"{k}={v}" for k, v in result.details.items())
        mismatch = "; ".join(
            f"{key}: expected={value['expected']} actual={value['actual']}"
            for key, value in result.mismatches.items()
        )
        lines.append(
            "| {name} | {passed} | {details} | {mismatch} |".format(
                name=_escape_pipe(result.name),
                passed="yes" if result.passed else "no",
                details=_escape_pipe(details or "-"),
                mismatch=_escape_pipe(mismatch or "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_pro_smoke_block_report(
    report: ProSmokeBlockValidationReport,
    *,
    out_dir: str | Path,
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "report_v1.json"
    md_path = out_path / "report_v1.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_pro_smoke_block_report_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_test_client(tmp_dir: Path) -> TestClient:
    db_path = tmp_dir / "jobdb.sqlite3"
    artifacts_dir = tmp_dir / "artifacts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    import os

    old_values = {
        "CHATGPTREST_DB_PATH": os.environ.get("CHATGPTREST_DB_PATH"),
        "CHATGPTREST_ARTIFACTS_DIR": os.environ.get("CHATGPTREST_ARTIFACTS_DIR"),
        "CHATGPTREST_PREVIEW_CHARS": os.environ.get("CHATGPTREST_PREVIEW_CHARS"),
        "CHATGPTREST_SAVE_CONVERSATION_EXPORT": os.environ.get("CHATGPTREST_SAVE_CONVERSATION_EXPORT"),
    }
    os.environ["CHATGPTREST_DB_PATH"] = str(db_path)
    os.environ["CHATGPTREST_ARTIFACTS_DIR"] = str(artifacts_dir)
    os.environ["CHATGPTREST_PREVIEW_CHARS"] = "10"
    os.environ["CHATGPTREST_SAVE_CONVERSATION_EXPORT"] = "0"
    try:
        return TestClient(create_app())
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _check_chatgpt_pro_smoke_override_blocked(client: TestClient) -> ProSmokeBlockCheckResult:
    response = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请帮我确认链路是否通了"},
            "params": {"preset": "pro_extended", "purpose": "smoke", "allow_pro_smoke_test": True},
        },
        headers={"Idempotency-Key": "phase14-chatgpt-pro-smoke"},
    )
    body = _safe_json(response)
    return _build_response_check(
        name="chatgpt_pro_smoke_override_blocked",
        response=response,
        body=body,
        expected_error="pro_smoke_test_blocked",
    )


def _check_chatgpt_pro_trivial_override_blocked(client: TestClient) -> ProSmokeBlockCheckResult:
    response = client.post(
        "/v1/jobs",
        json={
            "kind": "chatgpt_web.ask",
            "input": {"question": "请回复OK"},
            "params": {"preset": "pro_extended", "allow_trivial_pro_prompt": True},
        },
        headers={"Idempotency-Key": "phase14-chatgpt-pro-trivial"},
    )
    body = _safe_json(response)
    return _build_response_check(
        name="chatgpt_pro_trivial_override_blocked",
        response=response,
        body=body,
        expected_error="trivial_pro_prompt_blocked",
    )


def _check_gemini_pro_smoke_override_blocked(client: TestClient) -> ProSmokeBlockCheckResult:
    response = client.post(
        "/v1/jobs",
        json={
            "kind": "gemini_web.ask",
            "input": {"question": "quick probe"},
            "params": {"preset": "pro", "purpose": "smoke", "allow_pro_smoke_test": True},
        },
        headers={"Idempotency-Key": "phase14-gemini-pro-smoke"},
    )
    body = _safe_json(response)
    return _build_response_check(
        name="gemini_pro_smoke_override_blocked",
        response=response,
        body=body,
        expected_error="pro_smoke_test_blocked",
    )


def _check_active_docs_scrubbed() -> ProSmokeBlockCheckResult:
    mismatches: dict[str, dict[str, Any]] = {}
    details: dict[str, Any] = {}
    for rel_path in ACTIVE_DOCS_FOR_PRO_BLOCK:
        text = Path(rel_path).read_text(encoding="utf-8")
        found = [token for token in LEGACY_OVERRIDE_TOKENS if token in text]
        details[rel_path] = ",".join(found) if found else "clean"
        if found:
            mismatches[rel_path] = {"expected": "clean", "actual": found}
    return ProSmokeBlockCheckResult(
        name="active_docs_scrubbed",
        passed=not mismatches,
        details=details,
        mismatches=mismatches,
    )


def _build_response_check(
    *,
    name: str,
    response: Any,
    body: dict[str, Any],
    expected_error: str,
) -> ProSmokeBlockCheckResult:
    detail = body.get("detail") if isinstance(body, dict) else {}
    actual_error = _mapping(detail).get("error")
    details = {
        "http_status": int(response.status_code),
        "error": actual_error,
    }
    mismatches: dict[str, dict[str, Any]] = {}
    if int(response.status_code) != 400:
        mismatches["http_status"] = {"expected": 400, "actual": int(response.status_code)}
    if actual_error != expected_error:
        mismatches["error"] = {"expected": expected_error, "actual": actual_error}
    return ProSmokeBlockCheckResult(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _safe_json(response: Any) -> dict[str, Any]:
    try:
        parsed = response.json()
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")

