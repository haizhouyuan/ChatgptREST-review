from __future__ import annotations

import hashlib
import json
import time

from chatgptrest.advisor.feishu_handler import FeishuHandler, check_timestamp_freshness, verify_signature


def _signed_request(payload: dict, *, secret: str = "test-secret") -> tuple[bytes, dict[str, str]]:
    raw_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(time.time())
    nonce = "test-nonce"
    signature = hashlib.sha256(f"{timestamp}\n{nonce}\n{secret}\n".encode() + raw_body).hexdigest()
    return raw_body, {
        "X-Lark-Request-Timestamp": timestamp,
        "X-Lark-Request-Nonce": nonce,
        "X-Lark-Signature": signature,
    }


def test_verify_signature_fails_closed_without_secret() -> None:
    assert verify_signature(b"{}", str(time.time()), "nonce", "sig", "") is False


def test_timestamp_freshness_rejects_invalid_values() -> None:
    assert check_timestamp_freshness("not-a-number") is False


def test_signed_challenge_is_accepted() -> None:
    handler = FeishuHandler(webhook_secret="test-secret")
    payload = {"challenge": "challenge-123"}
    raw_body, headers = _signed_request(payload)

    result = handler.handle_webhook(payload, raw_body=raw_body, headers=headers)

    assert result == {"challenge": "challenge-123"}


def test_unsigned_challenge_is_rejected() -> None:
    handler = FeishuHandler(webhook_secret="test-secret")
    payload = {"challenge": "challenge-123"}

    result = handler.handle_webhook(payload, raw_body=b"{}", headers={})

    assert result["status"] == "error"
    assert result["code"] == 401
    assert result["reason"] == "signature_verification_failed"

