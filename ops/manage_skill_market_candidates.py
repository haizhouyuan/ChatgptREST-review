from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chatgptrest.kernel.market_gate import get_capability_gap_recorder
from ops.import_skill_market_candidates import import_market_source, list_market_sources


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _cmd_register(args: argparse.Namespace) -> int:
    recorder = get_capability_gap_recorder()
    candidate = recorder.register_market_candidate(
        skill_id=args.skill_id,
        source_market=args.source_market,
        source_uri=args.source_uri,
        capability_ids=args.capability or [],
        linked_gap_id=args.linked_gap_id or "",
        summary=args.summary or "",
        evidence={},
    )
    _print(candidate.to_dict())
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    recorder = get_capability_gap_recorder()
    if args.capability_id or args.linked_gap_id or args.trust_level:
        candidates = recorder.search_market_candidates(
            capability_id=args.capability_id or "",
            linked_gap_id=args.linked_gap_id or "",
            status=args.status or "",
            trust_level=args.trust_level or "",
            limit=args.limit,
        )
    else:
        candidates = recorder.list_market_candidates(status=args.status or "", limit=args.limit)
    _print([candidate.to_dict() for candidate in candidates])
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    recorder = get_capability_gap_recorder()
    candidate = recorder.evaluate_market_candidate(
        args.candidate_id,
        platform=args.platform,
        smoke_passed=args.smoke == "passed",
        compatibility_passed=args.compatibility == "passed",
        summary=args.summary,
    )
    _print(candidate.to_dict())
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    recorder = get_capability_gap_recorder()
    candidate = recorder.promote_market_candidate(
        args.candidate_id,
        promoted_by=args.promoted_by,
        real_use_trace_id=args.real_use_trace_id,
        real_use_notes=args.real_use_notes or "",
        close_linked_gap=not args.keep_gap_open,
    )
    _print(candidate.to_dict())
    return 0


def _cmd_deprecate(args: argparse.Namespace) -> int:
    recorder = get_capability_gap_recorder()
    candidate = recorder.deprecate_market_candidate(
        args.candidate_id,
        deprecated_by=args.deprecated_by,
        reason=args.reason,
        reopen_linked_gap=args.reopen_gap,
    )
    _print(candidate.to_dict())
    return 0


def _cmd_list_sources(args: argparse.Namespace) -> int:
    _print(list_market_sources(args.policy_path or ""))
    return 0


def _cmd_import_source(args: argparse.Namespace) -> int:
    result = import_market_source(
        args.source_id,
        manifest_uri=args.manifest_uri or "",
        allow_disabled=args.allow_disabled,
        policy_path=args.policy_path or "",
    )
    _print(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage skill-platform market candidates and quarantine lifecycle.")
    sub = parser.add_subparsers(dest="command", required=True)

    register = sub.add_parser("register", help="Register a new external skill candidate in quarantine.")
    register.add_argument("--skill-id", required=True)
    register.add_argument("--source-market", required=True)
    register.add_argument("--source-uri", required=True)
    register.add_argument("--capability", action="append", default=[])
    register.add_argument("--linked-gap-id", default="")
    register.add_argument("--summary", default="")
    register.set_defaults(func=_cmd_register)

    list_cmd = sub.add_parser("list", help="List recorded market skill candidates.")
    list_cmd.add_argument("--status", default="")
    list_cmd.add_argument("--capability-id", default="")
    list_cmd.add_argument("--linked-gap-id", default="")
    list_cmd.add_argument("--trust-level", default="")
    list_cmd.add_argument("--limit", type=int, default=100)
    list_cmd.set_defaults(func=_cmd_list)

    evaluate = sub.add_parser("evaluate", help="Record smoke/compatibility verdict for a candidate.")
    evaluate.add_argument("--candidate-id", required=True)
    evaluate.add_argument("--platform", required=True)
    evaluate.add_argument("--smoke", choices=("passed", "failed"), required=True)
    evaluate.add_argument("--compatibility", choices=("passed", "failed"), required=True)
    evaluate.add_argument("--summary", default="")
    evaluate.set_defaults(func=_cmd_evaluate)

    promote = sub.add_parser("promote", help="Promote a quarantine-approved candidate after real-use proof.")
    promote.add_argument("--candidate-id", required=True)
    promote.add_argument("--promoted-by", required=True)
    promote.add_argument("--real-use-trace-id", required=True)
    promote.add_argument("--real-use-notes", default="")
    promote.add_argument("--keep-gap-open", action="store_true")
    promote.set_defaults(func=_cmd_promote)

    deprecate = sub.add_parser("deprecate", help="Deprecate a promoted/evaluated market candidate.")
    deprecate.add_argument("--candidate-id", required=True)
    deprecate.add_argument("--deprecated-by", required=True)
    deprecate.add_argument("--reason", required=True)
    deprecate.add_argument("--reopen-gap", action="store_true")
    deprecate.set_defaults(func=_cmd_deprecate)

    list_sources = sub.add_parser("list-sources", help="List allowlisted market sources.")
    list_sources.add_argument("--policy-path", default="")
    list_sources.set_defaults(func=_cmd_list_sources)

    import_source = sub.add_parser("import-source", help="Import candidates from an allowlisted market source into quarantine.")
    import_source.add_argument("--source-id", required=True)
    import_source.add_argument("--manifest-uri", default="")
    import_source.add_argument("--policy-path", default="")
    import_source.add_argument("--allow-disabled", action="store_true")
    import_source.set_defaults(func=_cmd_import_source)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
