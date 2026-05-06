"""ConfigWatcher — background file-change-driven config hot-reload.

Polls the routing_profile.json mtime at a configurable interval.
When the file changes, it loads + validates the new config, then
atomically swaps it into the RoutingEngine via engine.reload().

If validation fails, the watcher logs the error and keeps the old config.

Usage::

    watcher = ConfigWatcher(engine, poll_interval_s=5)
    watcher.start()
    # ... later
    watcher.stop()
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chatgptrest.kernel.routing_engine import RoutingEngine

from chatgptrest.kernel.routing_config import DEFAULT_CONFIG_PATH, RoutingConfigError

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """Background config hot-reload watcher.

    Daemon thread polls file mtime, reloads on change, rolls back on error.
    """

    def __init__(
        self,
        engine: RoutingEngine,
        *,
        config_path: str | None = None,
        poll_interval_s: float = 5.0,
    ) -> None:
        self._engine = engine
        self._config_path = config_path or os.environ.get(
            "ROUTING_PROFILE_PATH", DEFAULT_CONFIG_PATH,
        )
        self._poll_interval = poll_interval_s
        self._last_mtime: float = 0.0
        self._running = False
        self._thread: threading.Thread | None = None
        self._reload_count: int = 0
        self._last_error: str | None = None

        # Initialize mtime
        try:
            self._last_mtime = os.path.getmtime(self._config_path)
        except OSError:
            pass

    @property
    def reload_count(self) -> int:
        """Number of successful reloads since start."""
        return self._reload_count

    @property
    def last_error(self) -> str | None:
        """Last error message from a failed reload attempt, or None."""
        return self._last_error

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="config-watcher",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "ConfigWatcher: started (path=%s, interval=%.1fs)",
            self._config_path, self._poll_interval,
        )

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._poll_interval * 2)
        self._thread = None
        logger.info("ConfigWatcher: stopped (reloads=%d)", self._reload_count)

    def check_now(self) -> bool:
        """Manually check for config change and reload if needed.

        Returns True if a reload was performed.
        """
        return self._check_and_reload()

    # ── Internal ──────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        """Main polling loop running in daemon thread."""
        while self._running:
            try:
                self._check_and_reload()
            except Exception as e:
                logger.error("ConfigWatcher: poll error: %s", e)
            time.sleep(self._poll_interval)

    def _check_and_reload(self) -> bool:
        """Check mtime and reload if changed. Returns True if reloaded."""
        try:
            current_mtime = os.path.getmtime(self._config_path)
        except OSError:
            return False

        if current_mtime <= self._last_mtime:
            return False

        # File changed — attempt reload
        logger.info(
            "ConfigWatcher: config changed (mtime %.0f → %.0f), reloading...",
            self._last_mtime, current_mtime,
        )

        try:
            self._engine.reload(self._config_path)
            self._last_mtime = current_mtime
            self._reload_count += 1
            self._last_error = None
            logger.info(
                "ConfigWatcher: reload #%d successful (engine v%d)",
                self._reload_count, self._engine.config_version,
            )
            return True

        except RoutingConfigError as e:
            self._last_error = str(e)
            self._last_mtime = current_mtime  # Don't retry same bad file
            logger.error(
                "ConfigWatcher: validation failed, keeping old config: %s", e,
            )
            return False

        except Exception as e:
            self._last_error = str(e)
            logger.error(
                "ConfigWatcher: reload failed, keeping old config: %s", e,
            )
            return False
