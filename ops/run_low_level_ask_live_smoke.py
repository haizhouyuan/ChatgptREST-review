#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chatgptrest.core.client_request_auth import build_registered_client_hmac_headers


_ENV_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _load_env_file(path: Path) -> dict[str, str]:
    env_map: dict[str, str] = {}
    if not path.is_file():
        return env_map
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE_RE.match(line)
        if not match:
            continue
        key = str(match.group(1) or "").strip()
        value = str(match.group(2) or "").strip()
        if len(value) >= 2 and value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        env_map[key] = value
    return env_map


def _resolve_tokens(args: argparse.Namespace) -> tuple[dict[str, str], str, str, str]:
    env_map = _load_env_file(Path(args.env_file).expanduser())
    explicit = str(args.bearer_token or "").strip()
    api_token = str(env_map.get("CHATGPTREST_API_TOKEN") or "").strip()
    ops_token = str(env_map.get("CHATGPTREST_OPS_TOKEN") or "").strip()
    preferred = explicit or api_token or ops_token
    return env_map, api_token, ops_token, preferred


def _request_json(*, url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: int) -> tuple[int, dict[str, str], Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                body = json.loads(raw) if raw.strip() else None
            except Exception:
                body = {"raw": raw[:4000]}
            return resp.getcode(), dict(resp.headers), body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw) if raw.strip() else None
        except Exception:
            body = {"raw": raw[:4000]}
        return exc.code, dict(exc.headers), body


def _request_headers(*, bearer_token: str, client_name: str, client_instance: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {bearer_token}",
        "Idempotency-Key": f"live-smoke-{uuid.uuid4().hex[:12]}",
        "User-Agent": "chatgptrest-low-level-live-smoke/1.0",
        "X-Client-Name": client_name,
        "X-Client-Instance": client_instance,
        "X-Request-ID": f"req-{uuid.uuid4().hex[:12]}",
    }


def _signed_request_headers(
    *,
    bearer_token: str,
    client_name: str,
    client_instance: str,
    payload: dict[str, Any],
    env_map: dict[str, str],
) -> dict[str, str]:
    headers = _request_headers(bearer_token=bearer_token, client_name=client_name, client_instance=client_instance)
    headers.update(
        build_registered_client_hmac_headers(
            client_lookup=client_name,
            client_instance=client_instance,
            method="POST",
            path="/v1/jobs",
            body_payload=payload,
            environ=env_map,
        )
    )
    return headers


def _detail(body: Any) -> dict[str, Any]:
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict):
            return detail
    return {}


def _check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live low-level ask smoke probes against the ChatgptREST API.")
    parser.add_argument("--api-base", default="http://127.0.0.1:18711")
    parser.add_argument("--env-file", default="~/.config/chatgptrest/chatgptrest.env")
    parser.add_argument("--bearer-token", default="")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--client-instance", default="low-level-live-smoke")
    args = parser.parse_args()

    env_map, api_token, ops_token, bearer_token = _resolve_tokens(args)
    if not bearer_token:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "missing_bearer_token",
                    "detail": "Provide --bearer-token or make CHATGPTREST_API_TOKEN / CHATGPTREST_OPS_TOKEN available in the env file.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    base = str(args.api_base or "").rstrip("/")
    timeout_seconds = max(10, int(args.timeout_seconds))
    client_instance = str(args.client_instance or "").strip() or "low-level-live-smoke"
    failures: list[str] = []

    unsigned_results: dict[str, Any] = {}
    token_paths: list[tuple[str, str]] = []
    if api_token:
        token_paths.append(("api_token", api_token))
    if ops_token and ops_token != api_token:
        token_paths.append(("ops_token_fallback", ops_token))
    if not token_paths and bearer_token:
        token_paths.append(("explicit_or_fallback", bearer_token))

    unsigned_probe_payload = {
        "kind": "gemini_web.ask",
        "input": {"question": "Please summarize three risks."},
        "params": {"preset": "auto"},
    }
    for token_label, token_value in token_paths:
        status, _headers, body = _request_json(
            url=f"{base}/v1/jobs",
            payload=unsigned_probe_payload,
            headers=_request_headers(
                bearer_token=token_value,
                client_name="chatgptrest-admin-mcp",
                client_instance=f"{client_instance}-{token_label}",
            ),
            timeout_seconds=timeout_seconds,
        )
        detail = _detail(body)
        unsigned_results[token_label] = {"status_code": status, "body": body}
        _check(status == 403, f"{token_label} unsigned admin probe expected 403, got {status}", failures)
        _check(
            detail.get("error") == "low_level_ask_client_auth_failed",
            f"{token_label} unsigned admin probe expected low_level_ask_client_auth_failed, got {detail.get('error')!r}",
            failures,
        )

    signed_payload = {
        "kind": "gemini_web.ask",
        "input": {
            "question": "Summarize three operational risks in migrating a billing service to Kubernetes with limited rehearsal and partial rollback coverage."
        },
        "params": {"preset": "auto"},
    }
    signed_results: dict[str, Any] = {}
    signed_probes = [
        ("chatgptrestctl-maint", api_token or bearer_token, "api_or_default"),
        ("chatgptrest-admin-mcp", ops_token or api_token or bearer_token, "ops_or_default"),
    ]
    for client_name, token_value, token_label in signed_probes:
        if not token_value:
            signed_results[client_name] = {"skipped": True, "reason": "no_bearer_token_available"}
            failures.append(f"{client_name} signed probe could not run because no bearer token was available")
            continue
        status, _headers, body = _request_json(
            url=f"{base}/v1/jobs",
            payload=signed_payload,
            headers=_signed_request_headers(
                bearer_token=token_value,
                client_name=client_name,
                client_instance=f"{client_instance}-{client_name}",
                payload=signed_payload,
                env_map=env_map,
            ),
            timeout_seconds=timeout_seconds,
        )
        signed_results[client_name] = {"token_path": token_label, "status_code": status, "body": body}
        _check(status == 200, f"{client_name} signed probe expected 200, got {status}", failures)
        _check(
            isinstance(body, dict) and bool(body.get("job_id")),
            f"{client_name} signed probe expected a non-empty job_id",
            failures,
        )

    planning_sufficiency_payload = {
        "kind": "chatgpt_web.ask",
        "input": {
            "question": "Only answer sufficient or insufficient. Determine whether the current material is sufficient to review the migration proposal."
        },
        "params": {"preset": "auto"},
    }
    planning_unsigned_status, _planning_unsigned_headers, planning_unsigned_body = _request_json(
        url=f"{base}/v1/jobs",
        payload=planning_sufficiency_payload,
        headers=_request_headers(
            bearer_token=bearer_token,
            client_name="planning-chatgptrest-call",
            client_instance=client_instance,
        ),
        timeout_seconds=timeout_seconds,
    )
    planning_unsigned_detail = _detail(planning_unsigned_body)
    _check(planning_unsigned_status == 403, f"unsigned planning probe expected 403, got {planning_unsigned_status}", failures)
    _check(
        planning_unsigned_detail.get("error") == "low_level_ask_client_auth_failed",
        f"unsigned planning probe expected low_level_ask_client_auth_failed, got {planning_unsigned_detail.get('error')!r}",
        failures,
    )

    sufficiency_status, _sufficiency_headers, sufficiency_body = _request_json(
        url=f"{base}/v1/jobs",
        payload=planning_sufficiency_payload,
        headers=_signed_request_headers(
            bearer_token=bearer_token,
            client_name="planning-chatgptrest-call",
            client_instance=f"{client_instance}-planning",
            payload=planning_sufficiency_payload,
            env_map=env_map,
        ),
        timeout_seconds=timeout_seconds,
    )
    sufficiency_detail = _detail(sufficiency_body)
    _check(sufficiency_status == 403, f"signed planning sufficiency-gate probe expected 403, got {sufficiency_status}", failures)
    _check(
        sufficiency_detail.get("reason") == "sufficiency_gate",
        f"signed planning sufficiency-gate probe expected reason sufficiency_gate, got {sufficiency_detail.get('reason')!r}",
        failures,
    )

    planning_substantive_payload = {
        "kind": "chatgpt_web.ask",
        "input": {
            "question": (
                "Respond with JSON only using keys summary, risks, mitigations, readiness.\n"
                "Review this migration proposal:\n"
                "- Move the billing service from a single VM to Kubernetes over two weekends.\n"
                "- Freeze schema changes for 48 hours, but keep customer-facing deploys enabled.\n"
                "- Keep rollback as DNS cutback to the old VM; database writes are dual-written only for premium customers.\n"
                "- Observability will be added after cutover if latency increases.\n"
                "- One SRE and one backend engineer are on-call; no rehearsal is planned.\n"
                "Explain the operational, delivery, and rollback risks."
            )
        },
        "params": {"preset": "auto"},
    }
    substantive_status, _substantive_headers, substantive_body = _request_json(
        url=f"{base}/v1/jobs",
        payload=planning_substantive_payload,
        headers=_signed_request_headers(
            bearer_token=bearer_token,
            client_name="planning-chatgptrest-call",
            client_instance=f"{client_instance}-planning-substantive",
            payload=planning_substantive_payload,
            env_map=env_map,
        ),
        timeout_seconds=timeout_seconds,
    )
    _check(substantive_status == 200, f"substantive planning review expected 200, got {substantive_status}", failures)
    _check(
        isinstance(substantive_body, dict) and bool(substantive_body.get("job_id")),
        "substantive planning review expected a non-empty job_id",
        failures,
    )
    duplicate_status, _duplicate_headers, duplicate_body = _request_json(
        url=f"{base}/v1/jobs",
        payload=planning_substantive_payload,
        headers=_signed_request_headers(
            bearer_token=bearer_token,
            client_name="planning-chatgptrest-call",
            client_instance=f"{client_instance}-planning-substantive",
            payload=planning_substantive_payload,
            env_map=env_map,
        ),
        timeout_seconds=timeout_seconds,
    )
    duplicate_detail = _detail(duplicate_body)
    _check(duplicate_status == 409, f"duplicate planning review expected 409, got {duplicate_status}", failures)
    _check(
        duplicate_detail.get("error") == "low_level_ask_duplicate_recently_submitted",
        f"duplicate planning review expected low_level_ask_duplicate_recently_submitted, got {duplicate_detail.get('error')!r}",
        failures,
    )

    openclaw_status, _openclaw_headers, openclaw_body = _request_json(
        url=f"{base}/v1/jobs",
        payload=planning_substantive_payload,
        headers=_request_headers(
            bearer_token=bearer_token,
            client_name="openclaw-chatgptrest-call",
            client_instance=f"{client_instance}-openclaw",
        ),
        timeout_seconds=timeout_seconds,
    )
    openclaw_detail = _detail(openclaw_body)
    _check(openclaw_status == 403, f"openclaw low-level probe expected 403, got {openclaw_status}", failures)
    _check(
        openclaw_detail.get("error") == "low_level_ask_surface_not_allowed",
        f"openclaw low-level probe expected low_level_ask_surface_not_allowed, got {openclaw_detail.get('error')!r}",
        failures,
    )

    advisor_status, _advisor_headers, advisor_body = _request_json(
        url=f"{base}/v1/jobs",
        payload=signed_payload,
        headers=_request_headers(
            bearer_token=bearer_token,
            client_name="advisor_ask",
            client_instance=f"{client_instance}-advisor",
        ),
        timeout_seconds=timeout_seconds,
    )
    advisor_detail = _detail(advisor_body)
    _check(advisor_status == 403, f"advisor alias low-level probe expected 403, got {advisor_status}", failures)
    _check(
        advisor_detail.get("error") == "low_level_ask_surface_not_allowed",
        f"advisor alias low-level probe expected low_level_ask_surface_not_allowed, got {advisor_detail.get('error')!r}",
        failures,
    )

    result = {
        "ok": not failures,
        "api_base": base,
        "token_source": ("explicit" if str(args.bearer_token or "").strip() else str(Path(args.env_file).expanduser())),
        "token_availability": {
            "api_token_present": bool(api_token),
            "ops_token_present": bool(ops_token),
            "ops_token_distinct_from_api": bool(api_token and ops_token and api_token != ops_token),
        },
        "unsigned_maintenance": unsigned_results,
        "signed_maintenance": signed_results,
        "planning_unsigned": {"status_code": planning_unsigned_status, "body": planning_unsigned_body},
        "planning_sufficiency_gate": {"status_code": sufficiency_status, "body": sufficiency_body},
        "planning_substantive_review": {"status_code": substantive_status, "body": substantive_body},
        "planning_duplicate_review": {"status_code": duplicate_status, "body": duplicate_body},
        "openclaw_low_level_probe": {"status_code": openclaw_status, "body": openclaw_body},
        "advisor_alias_low_level_probe": {"status_code": advisor_status, "body": advisor_body},
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
