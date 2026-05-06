from __future__ import annotations

import json
from pathlib import Path

from chatgptrest.telemetry_contract import extract_identity_fields


FIXTURE_DIR = Path("docs/dev_log/artifacts/execution_extension_fixture_bundle_20260311")
SPLIT_SPEC = FIXTURE_DIR / "normalization_field_split_v1.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_execution_extension_fixture_bundle_matches_identity_normalization() -> None:
    spec = _load_json(SPLIT_SPEC)
    fixtures = spec["fixtures"]
    assert fixtures, "fixture bundle should not be empty"

    for fixture in fixtures:
        payload = _load_json(FIXTURE_DIR / fixture["source_file"])
        expected = fixture["normalized_identity"]
        identity = extract_identity_fields(payload)

        root = expected["root_canonical"]
        for key, value in root.items():
            assert identity.get(key) == value, f"{fixture['fixture_id']} root field mismatch: {key}"

        extensions = expected["execution_extensions"]
        for key, value in extensions.items():
            assert identity.get(key) == value, f"{fixture['fixture_id']} extension mismatch: {key}"

        all_expected = {**root, **extensions}
        untouched_extension_keys = {
            "lane_id",
            "role_id",
            "adapter_id",
            "profile_id",
            "executor_kind",
        } - set(extensions.keys())
        for key in untouched_extension_keys:
            assert identity.get(key) in (None, ""), f"{fixture['fixture_id']} unexpected extension value for {key}"
        for key in ("event_type", "source", "trace_id", "session_id"):
            assert key in all_expected
