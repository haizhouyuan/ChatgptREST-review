from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path("ops/smoke_test_chatgpt_auto.py").resolve()
    spec = importlib.util.spec_from_file_location("smoke_test_chatgpt_auto_test", path)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_policy_blocks_live_chatgpt_smoke_by_default() -> None:
    mod = _load_module()
    err = mod._policy_error_for_args(preset="auto", allow_live_chatgpt_smoke=False)
    assert err is not None
    assert err["error_type"] == "PolicyError"
    assert "blocked by default" in err["message"]


def test_policy_blocks_high_cost_preset() -> None:
    mod = _load_module()
    err = mod._policy_error_for_args(preset="pro_extended", allow_live_chatgpt_smoke=True)
    assert err is not None
    assert "only permits preset=auto" in err["message"]


def test_policy_allows_controlled_auto_override() -> None:
    mod = _load_module()
    err = mod._policy_error_for_args(preset="auto", allow_live_chatgpt_smoke=True)
    assert err is None
