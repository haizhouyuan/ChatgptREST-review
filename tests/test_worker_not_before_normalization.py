from __future__ import annotations

import chatgptrest.worker.worker as worker_mod


def test_coerce_retry_not_before_rejects_monotonic_style_values() -> None:
    now = 1_772_850_000.0
    out = worker_mod._coerce_retry_not_before(7316.934368818, retry_after=30, now=now)
    assert out == now + 30.0


def test_coerce_retry_not_before_preserves_valid_epoch_seconds() -> None:
    now = 1_772_850_000.0
    valid = now + 45.0
    out = worker_mod._coerce_retry_not_before(valid, retry_after=30, now=now)
    assert out == valid


def test_coerce_retry_not_before_falls_back_for_nan() -> None:
    now = 1_772_850_000.0
    out = worker_mod._coerce_retry_not_before(float("nan"), retry_after=15, now=now)
    assert out == now + 15.0
