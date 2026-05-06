"""LLM bridge for AtomRefiner — uses Codex CLI (gpt-5.4-high) for fast,
cost-effective atom refinement.

Usage::

    from chatgptrest.evomap.knowledge.llm_bridge import CodexBridge, BridgeConfig

    bridge = CodexBridge(config=BridgeConfig(model="o3"))
    answer = bridge.call(prompt, system_prompt)

    # Use with AtomRefiner:
    refiner = AtomRefiner(db=db, llm_fn=bridge.call, config=refiner_config)
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chatgptrest.core.codex_runner import codex_exec_with_schema, CodexExecResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class BridgeConfig:
    """Configuration for CodexBridge."""
    model: str = "gpt-5.4"           # Codex model (gpt-5.4 = ChatGPT 5.4)
    reasoning_effort: str = "high"   # low / medium / high
    timeout_seconds: int = 180       # per-call timeout (5.4 high can take time)
    sandbox: str = "read-only"       # codex sandbox mode
    min_call_interval: float = 1.0   # minimum seconds between calls
    schema_dir: str = ""             # directory for temp schema files


# ---------------------------------------------------------------------------
# JSON Schema for atom refinement output
# ---------------------------------------------------------------------------

_REFINEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "refinements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "atom_id": {"type": "string"},
                    "question": {"type": "string"},
                    "canonical_question": {"type": "string"},
                    "atom_type": {
                        "type": "string",
                        "enum": ["qa", "decision", "procedure", "troubleshooting", "lesson"],
                    },
                    "quality_auto": {"type": "number"},
                    "novelty": {"type": "number"},
                    "groundedness": {"type": "number"},
                    "reusability": {"type": "number"},
                    "confidence": {"type": "number"},
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "atom_id", "question", "canonical_question",
                    "atom_type", "quality_auto", "novelty",
                    "groundedness", "reusability", "confidence",
                    "constraints",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["refinements"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# CodexBridge
# ---------------------------------------------------------------------------

class CodexBridge:
    """LLM bridge that uses Codex CLI for structured atom refinement.

    Compatible with AtomRefiner's ``llm_fn(prompt, system) -> str`` signature.
    Internally uses ``codex exec --output-schema`` to get structured JSON,
    then converts back to the JSON string AtomRefiner expects.
    """

    def __init__(self, config: BridgeConfig | None = None):
        self._config = config or BridgeConfig()
        self._last_call_time: float = 0.0
        self._stats: dict[str, Any] = {
            "call_count": 0,
            "total_elapsed_ms": 0,
            "errors": 0,
        }
        self._schema_path: Path | None = None

    @property
    def stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def _ensure_schema(self) -> Path:
        """Write the JSON schema to a temp file (once)."""
        if self._schema_path and self._schema_path.exists():
            return self._schema_path

        schema_dir = self._config.schema_dir or tempfile.gettempdir()
        path = Path(schema_dir) / "atom_refinement_schema.json"
        path.write_text(
            json.dumps(_REFINEMENT_SCHEMA, indent=2),
            encoding="utf-8",
        )
        self._schema_path = path
        logger.debug("Schema written to %s", path)
        return path

    def _rate_limit(self) -> None:
        """Enforce minimum interval between calls."""
        if self._last_call_time > 0:
            elapsed = time.time() - self._last_call_time
            wait = self._config.min_call_interval - elapsed
            if wait > 0:
                time.sleep(wait)
        self._last_call_time = time.time()

    def call(self, prompt: str, system: str) -> str:
        """Execute LLM call via Codex CLI.

        Args:
            prompt: The user prompt (batch of atoms to refine).
            system: System prompt (domain instructions).

        Returns:
            JSON string that AtomRefiner._parse_refinements can parse.
        """
        self._rate_limit()

        schema_path = self._ensure_schema()
        out_json = Path(tempfile.mktemp(suffix=".json", prefix="atom_refine_"))

        # Combine system + user prompt for codex exec
        full_prompt = f"{system}\n\n---\n\n{prompt}"

        logger.info(
            "CodexBridge: calling codex exec (model=%s, prompt=%d chars)",
            self._config.model, len(full_prompt),
        )

        config_overrides = []
        if self._config.reasoning_effort:
            config_overrides.append(
                f'model_reasoning_effort="{self._config.reasoning_effort}"'
            )

        result: CodexExecResult = codex_exec_with_schema(
            prompt=full_prompt,
            schema_path=schema_path,
            out_json=out_json,
            model=self._config.model,
            timeout_seconds=self._config.timeout_seconds,
            sandbox=self._config.sandbox,
            config_overrides=config_overrides or None,
        )

        self._stats["call_count"] += 1
        self._stats["total_elapsed_ms"] += result.elapsed_ms

        if not result.ok:
            self._stats["errors"] += 1
            error_msg = result.error or "unknown codex error"
            logger.error(
                "CodexBridge: codex exec failed (rc=%s, %dms): %s",
                result.returncode, result.elapsed_ms, error_msg,
            )
            raise RuntimeError(f"Codex exec failed: {error_msg}")

        # Extract refinements from structured output
        output = result.output or {}
        refinements = output.get("refinements", [])

        logger.info(
            "CodexBridge: success (%dms, %d refinements)",
            result.elapsed_ms, len(refinements),
        )

        # Clean up temp file
        try:
            out_json.unlink(missing_ok=True)
        except Exception:
            pass

        # Return as JSON string for AtomRefiner._parse_refinements
        return json.dumps(refinements, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Legacy alias — keep the old name working for run_atom_refinement.py
# ---------------------------------------------------------------------------

ChatgptRESTBridge = CodexBridge
