"""Final scoped-launch gate for the premium agent ingress blueprint."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_API_BASE_URL = "http://127.0.0.1:18711"
DEFAULT_ENV_FILE = Path.home() / ".config" / "chatgptrest" / "chatgptrest.env"

GOOGLE_WORKSPACE_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "google_workspace_surface_validation_20260323"
PHASE10_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase10_controller_route_parity_validation_20260322"
PHASE11_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase11_branch_coverage_validation_20260322"
LIVE_CUTOVER_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "public_agent_live_cutover_validation_20260323"
EFFECTS_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "public_agent_effects_delivery_validation_20260323"
PHASE27_DIR = DEFAULT_REPO_ROOT / "docs" / "dev_log" / "artifacts" / "phase27_premium_default_path_validation_20260323"
CONFIG_CHECKER = DEFAULT_REPO_ROOT / "ops" / "check_public_mcp_client_configs.py"


@dataclass
class PremiumAgentBlueprintGateCheck:
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
class PremiumAgentBlueprintGateReport:
    base_url: str
    overall_passed: bool
    num_checks: int
    num_passed: int
    num_failed: int
    checks: list[PremiumAgentBlueprintGateCheck]
    scope_boundary: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "overall_passed": self.overall_passed,
            "num_checks": self.num_checks,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "checks": [item.to_dict() for item in self.checks],
            "scope_boundary": list(self.scope_boundary),
        }


def run_premium_agent_blueprint_scoped_launch_gate(
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    env_file: Path = DEFAULT_ENV_FILE,
) -> PremiumAgentBlueprintGateReport:
    workspace_report = _read_json(_latest_report_json(GOOGLE_WORKSPACE_DIR))
    phase10_report = _read_json(_latest_report_json(PHASE10_DIR))
    phase11_report = _read_json(_latest_report_json(PHASE11_DIR))
    live_cutover_report = _read_json(_latest_report_json(LIVE_CUTOVER_DIR))
    effects_report = _read_json(_latest_report_json(EFFECTS_DIR))
    phase27_report = _read_json(_latest_report_json(PHASE27_DIR))
    config_report = _run_config_checker()

    tokens = _load_tokens(env_file)
    auth_header = _build_auth_header(tokens)
    blocked_probe = _post_turn(
        base_url=base_url,
        headers={
            **auth_header,
            "X-Client-Name": "codex",
            "X-Client-Instance": "phase28-blueprint-gate",
            "X-Request-ID": str(uuid.uuid4()),
        },
    )

    checks = [
        _build_check(
            name="public_mcp_client_configs_aligned",
            details={
                "ok": bool(config_report.get("ok") or False),
                "num_checked": int(config_report.get("num_checked") or 0),
                "num_failed": int(config_report.get("num_failed") or 0),
            },
            expectations={"ok": True, "num_failed": 0},
        ),
        _build_check(
            name="coding_agent_direct_rest_blocked_live",
            details={
                "status_code": int(blocked_probe.get("status_code") or 0),
                "error": str(blocked_probe.get("error") or ""),
                "blocked": str(blocked_probe.get("error") or "") in {"client_not_allowed", "coding_agent_direct_rest_blocked"},
            },
            expectations={"status_code": 403, "blocked": True},
        ),
        _build_check(
            name="workspace_live_auth_ready",
            details={
                "num_failed": int(workspace_report.get("num_failed") or 0),
                "num_checks": int(workspace_report.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="heavy_execution_explicit_only_controller_parity",
            details={
                "num_failed": int(phase10_report.get("num_failed") or 0),
                "num_items": int(phase10_report.get("num_items") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="heavy_execution_explicit_only_branch_coverage",
            details={
                "num_failed": int(phase11_report.get("num_failed") or 0),
                "num_checks": int(phase11_report.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="public_agent_live_cutover_green",
            details={
                "num_failed": int(live_cutover_report.get("num_failed") or 0),
                "num_checks": int(live_cutover_report.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="public_agent_effects_delivery_green",
            details={
                "num_failed": int(effects_report.get("num_failed") or 0),
                "num_checks": int(effects_report.get("num_checks") or 0),
            },
            expectations={"num_failed": 0},
        ),
        _build_check(
            name="premium_default_path_regression_green",
            details={
                "num_failed": int(phase27_report.get("num_failed") or 0),
                "num_items": int(phase27_report.get("num_items") or 0),
            },
            expectations={"num_failed": 0},
        ),
    ]
    num_passed = sum(1 for item in checks if item.passed)
    return PremiumAgentBlueprintGateReport(
        base_url=str(base_url).rstrip("/"),
        overall_passed=num_passed == len(checks),
        num_checks=len(checks),
        num_passed=num_passed,
        num_failed=len(checks) - num_passed,
        checks=checks,
        scope_boundary=[
            "premium-agent ingress/control-plane blueprint is ready for scoped launch",
            "public MCP remains the northbound default for coding agents",
            "coding-agent direct REST is technically blocked on the live public surface",
            "ordinary premium asks remain on LLM default paths",
            "heavy execution stays explicit-only and not default",
            "google workspace live auth readiness is included",
            "not a full-stack deployment proof",
            "not an external provider completion proof",
            "not a heavy execution lane approval",
        ],
    )


def render_premium_agent_blueprint_scoped_launch_gate_markdown(report: PremiumAgentBlueprintGateReport) -> str:
    lines = [
        "# Premium Agent Blueprint Scoped Launch Gate Report",
        "",
        f"- base_url: {report.base_url}",
        f"- overall_passed: {str(report.overall_passed).lower()}",
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


def write_premium_agent_blueprint_scoped_launch_gate_report(
    report: PremiumAgentBlueprintGateReport,
    *,
    out_dir: str | Path,
    basename: str = "report_v1",
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / f"{basename}.json"
    md_path = out_path / f"{basename}.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_premium_agent_blueprint_scoped_launch_gate_markdown(report), encoding="utf-8")
    return json_path, md_path


def _build_check(*, name: str, details: dict[str, Any], expectations: dict[str, Any]) -> PremiumAgentBlueprintGateCheck:
    mismatches: dict[str, dict[str, Any]] = {}
    for field_name, expected in expectations.items():
        actual = details.get(field_name)
        if actual != expected:
            mismatches[field_name] = {"expected": expected, "actual": actual}
    return PremiumAgentBlueprintGateCheck(name=name, passed=not mismatches, details=details, mismatches=mismatches)


def _latest_report_json(directory: Path) -> Path:
    pattern = re.compile(r"report_v(\d+)\.json$")
    candidates: list[tuple[int, Path]] = []
    for path in directory.glob("report_v*.json"):
        match = pattern.match(path.name)
        if not match:
            continue
        candidates.append((int(match.group(1)), path))
    if not candidates:
        raise FileNotFoundError(f"no report_v*.json found under {directory}")
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _run_config_checker() -> dict[str, Any]:
    proc = subprocess.run(
        ["python3", str(CONFIG_CHECKER)],
        cwd=str(DEFAULT_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    text = (proc.stdout or "").strip()
    parsed = json.loads(text) if text else {}
    return parsed if isinstance(parsed, dict) else {}


def _load_tokens(env_file: Path) -> dict[str, str]:
    values = {
        "OPENMIND_API_KEY": os.environ.get("OPENMIND_API_KEY", "").strip(),
        "CHATGPTREST_API_TOKEN": os.environ.get("CHATGPTREST_API_TOKEN", "").strip(),
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
    return values


def _build_auth_header(tokens: dict[str, str]) -> dict[str, str]:
    if tokens.get("OPENMIND_API_KEY"):
        return {"X-Api-Key": tokens["OPENMIND_API_KEY"]}
    if tokens.get("CHATGPTREST_API_TOKEN"):
        return {"Authorization": f"Bearer {tokens['CHATGPTREST_API_TOKEN']}"}
    raise RuntimeError("no local auth token available for premium blueprint gate")


def _post_turn(*, base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(
        str(base_url).rstrip("/") + "/v3/agent/turn",
        data=json.dumps({"message": "请总结面试纪要", "goal_hint": "planning"}, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.status
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    body = json.loads(text) if text.strip() else {}
    detail = body.get("detail") if isinstance(body, dict) else {}
    detail_map = detail if isinstance(detail, dict) else {}
    provenance = body.get("provenance") if isinstance(body, dict) else {}
    provenance_map = provenance if isinstance(provenance, dict) else {}
    return {
        "status_code": status_code,
        "error": detail_map.get("error") or (detail if isinstance(detail, str) else ""),
        "route": provenance_map.get("route") or body.get("route") if isinstance(body, dict) else "",
        "agent_status": body.get("status") if isinstance(body, dict) else "",
    }


def _escape_pipe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")
