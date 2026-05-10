from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api import PaperclipClient
from .validators import (
    validate_approval_record,
    validate_closeout,
    validate_config_gate_bundle,
    validate_evidence_manifest,
    validate_json_tree,
    validate_real_agent_loop,
    validate_operator_truth,
    validate_operator_truth_detailed,
    verify_full_manifest,
    verify_live_readback,
    verify_recursive_packet_manifests,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_validate_closeout(args: argparse.Namespace) -> int:
    errors = validate_closeout(Path(args.path), base=Path(args.base) if args.base else None)
    result = {"status": "pass" if not errors else "fail", "errors": errors}
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def cmd_validate_json_tree(args: argparse.Namespace) -> int:
    errors = validate_json_tree(Path(args.root))
    result = {"status": "pass" if not errors else "fail", "errors": errors}
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def cmd_validate_config_gate(args: argparse.Namespace) -> int:
    errors = validate_config_gate_bundle(Path(args.root))
    result = {"status": "pass" if not errors else "fail", "errors": errors}
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def cmd_validate_approval(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    errors = validate_approval_record(data)
    result = {"status": "pass" if not errors else "fail", "errors": errors}
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def cmd_validate_operator_truth(args: argparse.Namespace) -> int:
    result = validate_operator_truth_detailed(
        operator_json=Path(args.operator_json),
        current_truth=Path(args.current_truth),
        closeout=Path(args.closeout),
        blocker_board=Path(args.blocker_board),
    )
    if args.paperclip_base_url and args.parent_issues:
        client = PaperclipClient(args.paperclip_base_url, api_key=args.paperclip_api_key)
        parent_ids = [item.strip() for item in args.parent_issues.split(",") if item.strip()]
        allowed_statuses = {
            item.strip()
            for item in (args.parent_allowed_statuses or "done").split(",")
            if item.strip()
        }
        parent_rows = []
        parent_errors = []
        for issue_key in parent_ids:
            try:
                issue = client.get(f"issues/{issue_key}")
            except Exception as exc:  # noqa: BLE001
                parent_errors.append(f"live parent issue {issue_key} readback failed: {exc}")
                continue
            row = {
                "issue": issue_key,
                "issue_id": issue.get("id"),
                "status": issue.get("status"),
                "updatedAt": issue.get("updatedAt"),
                "completedAt": issue.get("completedAt"),
            }
            parent_rows.append(row)
            if issue.get("status") not in allowed_statuses:
                parent_errors.append(
                    f"live parent issue {issue_key} has status {issue.get('status')}, "
                    f"expected one of {sorted(allowed_statuses)}"
                )
        if args.parent_closeout:
            closeout_path = Path(args.parent_closeout)
            if not closeout_path.exists():
                parent_errors.append(f"parent closeout artifact missing: {closeout_path}")
        result["live_parent_issue_readback"] = parent_rows
        result.setdefault("rules", {})["no_unexplained_blocked_parent_issue_live_api"] = (
            "pass" if not parent_errors else "fail"
        )
        result["errors"].extend(parent_errors)
        result["status"] = "pass" if not result["errors"] else "fail"
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


def cmd_validate_evidence_manifest(args: argparse.Namespace) -> int:
    errors = validate_evidence_manifest(Path(args.path))
    result = {"status": "pass" if not errors else "fail", "errors": errors}
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def cmd_validate_real_agent_loop(args: argparse.Namespace) -> int:
    result = validate_real_agent_loop(Path(args.root))
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


def cmd_verify_full_manifest(args: argparse.Namespace) -> int:
    result = verify_full_manifest(Path(args.path))
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


def cmd_verify_live_readback(args: argparse.Namespace) -> int:
    client = PaperclipClient(args.paperclip_base_url, api_key=args.paperclip_api_key)
    result = verify_live_readback(Path(args.path), client)
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


def cmd_verify_recursive_packet_manifests(args: argparse.Namespace) -> int:
    result = verify_recursive_packet_manifests(
        root=Path(args.root),
        manifest=Path(args.manifest),
        nested=[Path(item) for item in args.nested],
    )
    if args.output:
        _write_json(Path(args.output), result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


def cmd_issue_matrix(args: argparse.Namespace) -> int:
    client = PaperclipClient(args.base_url)
    issues = client.get(f"companies/{args.company_id}/issues", {"limit": str(args.limit)})
    selected = []
    prefixes = tuple(args.prefix or [])
    for issue in issues:
        identifier = issue.get("identifier") or ""
        if prefixes and not identifier.startswith(prefixes):
            continue
        selected.append(
            {
                "identifier": identifier,
                "id": issue.get("id"),
                "title": issue.get("title"),
                "status": issue.get("status"),
                "assignee_agent_id": issue.get("assigneeAgentId"),
                "project_id": issue.get("projectId"),
                "updated_at": issue.get("updatedAt"),
            }
        )
    if args.output:
        _write_json(Path(args.output), selected)
    else:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paperclip-company-os")
    sub = parser.add_subparsers(dest="command", required=True)

    closeout = sub.add_parser("validate-closeout")
    closeout.add_argument("path")
    closeout.add_argument("--base")
    closeout.add_argument("--output")
    closeout.set_defaults(func=cmd_validate_closeout)

    tree = sub.add_parser("validate-json-tree")
    tree.add_argument("root")
    tree.add_argument("--output")
    tree.set_defaults(func=cmd_validate_json_tree)

    config_gate = sub.add_parser("validate-config-gate")
    config_gate.add_argument("root")
    config_gate.add_argument("--output")
    config_gate.set_defaults(func=cmd_validate_config_gate)

    approval = sub.add_parser("validate-approval")
    approval.add_argument("path")
    approval.add_argument("--output")
    approval.set_defaults(func=cmd_validate_approval)

    operator_truth = sub.add_parser("validate-operator-truth")
    operator_truth.add_argument("--operator-json", required=True)
    operator_truth.add_argument("--current-truth", required=True)
    operator_truth.add_argument("--closeout", required=True)
    operator_truth.add_argument("--blocker-board", required=True)
    operator_truth.add_argument("--paperclip-base-url")
    operator_truth.add_argument("--paperclip-api-key")
    operator_truth.add_argument("--parent-issues")
    operator_truth.add_argument("--parent-allowed-statuses")
    operator_truth.add_argument("--parent-closeout")
    operator_truth.add_argument("--output")
    operator_truth.set_defaults(func=cmd_validate_operator_truth)

    evidence_manifest = sub.add_parser("validate-evidence-manifest")
    evidence_manifest.add_argument("path")
    evidence_manifest.add_argument("--output")
    evidence_manifest.set_defaults(func=cmd_validate_evidence_manifest)

    real_agent_loop = sub.add_parser("validate-real-agent-loop")
    real_agent_loop.add_argument("root")
    real_agent_loop.add_argument("--output")
    real_agent_loop.set_defaults(func=cmd_validate_real_agent_loop)

    full_manifest = sub.add_parser("verify-full-manifest")
    full_manifest.add_argument("path")
    full_manifest.add_argument("--output")
    full_manifest.set_defaults(func=cmd_verify_full_manifest)

    live_readback = sub.add_parser("verify-live-readback")
    live_readback.add_argument("path")
    live_readback.add_argument("--paperclip-base-url", default="http://127.0.0.1:3100/api")
    live_readback.add_argument("--paperclip-api-key")
    live_readback.add_argument("--output")
    live_readback.set_defaults(func=cmd_verify_live_readback)

    recursive_packet = sub.add_parser("verify-recursive-packet-manifests")
    recursive_packet.add_argument("--root", required=True)
    recursive_packet.add_argument("--manifest", required=True)
    recursive_packet.add_argument("--nested", action="append", required=True)
    recursive_packet.add_argument("--output")
    recursive_packet.set_defaults(func=cmd_verify_recursive_packet_manifests)

    matrix = sub.add_parser("issue-matrix")
    matrix.add_argument("--base-url", default="http://127.0.0.1:3100/api")
    matrix.add_argument("--company-id", required=True)
    matrix.add_argument("--prefix", action="append")
    matrix.add_argument("--limit", type=int, default=100)
    matrix.add_argument("--output")
    matrix.set_defaults(func=cmd_issue_matrix)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
