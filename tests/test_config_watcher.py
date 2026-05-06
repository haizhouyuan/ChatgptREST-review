"""Tests for ConfigWatcher — hot-reload watcher."""

from __future__ import annotations

import json
import time
import pytest

# v1.0 routing modules deprecated — tests replaced by test_routing_fabric.py
pytestmark = pytest.mark.skip(reason="v1.0 routing modules deprecated")
import time

from chatgptrest.kernel.routing_config import load_routing_profile
from chatgptrest.kernel.routing_engine import RoutingEngine
from chatgptrest.kernel.config_watcher import ConfigWatcher


def test_start_stop():
    engine = RoutingEngine(load_routing_profile())
    watcher = ConfigWatcher(engine, poll_interval_s=0.1)
    assert not watcher.is_running
    watcher.start()
    assert watcher.is_running
    watcher.stop()
    assert not watcher.is_running


def test_reload_count_starts_at_zero():
    engine = RoutingEngine(load_routing_profile())
    watcher = ConfigWatcher(engine, poll_interval_s=60)
    assert watcher.reload_count == 0
    assert watcher.last_error is None


def test_check_now_no_change():
    engine = RoutingEngine(load_routing_profile())
    watcher = ConfigWatcher(engine, poll_interval_s=60)
    # No file change since construction
    did_reload = watcher.check_now()
    assert did_reload is False
    assert watcher.reload_count == 0


def test_detects_mtime_change(tmp_path):
    """Writes a valid config to tmp, then modifies it — watcher should detect."""
    # Write initial config
    profile = load_routing_profile()
    import chatgptrest.kernel.routing_config as rc
    config_path = tmp_path / "routing_profile.json"

    # Read original JSON
    with open(rc.DEFAULT_CONFIG_PATH, "r") as f:
        raw = json.load(f)
    config_path.write_text(json.dumps(raw, indent=2))

    engine = RoutingEngine(load_routing_profile(str(config_path)))
    watcher = ConfigWatcher(engine, config_path=str(config_path), poll_interval_s=60)

    # No change yet
    assert watcher.check_now() is False

    # Modify the file (touch to change mtime)
    time.sleep(0.05)
    raw["profile_name"] = "test_modified"
    config_path.write_text(json.dumps(raw, indent=2))

    # Now should detect and reload
    assert watcher.check_now() is True
    assert watcher.reload_count == 1
    assert engine.profile.profile_name == "test_modified"
    assert engine.config_version == 2


def test_ignores_invalid_config(tmp_path):
    """Bad JSON config → watcher logs error but keeps old config."""
    config_path = tmp_path / "routing_profile.json"

    # Write valid config first
    import chatgptrest.kernel.routing_config as rc
    with open(rc.DEFAULT_CONFIG_PATH, "r") as f:
        raw = json.load(f)
    config_path.write_text(json.dumps(raw, indent=2))

    engine = RoutingEngine(load_routing_profile(str(config_path)))
    old_name = engine.profile.profile_name
    watcher = ConfigWatcher(engine, config_path=str(config_path), poll_interval_s=60)

    # Write invalid config (empty routes fails validation)
    time.sleep(0.05)
    bad = {"routes": [], "providers": {}}
    config_path.write_text(json.dumps(bad))

    assert watcher.check_now() is False  # reload failed
    assert watcher.last_error is not None
    assert "No routes" in watcher.last_error
    assert engine.profile.profile_name == old_name  # unchanged
