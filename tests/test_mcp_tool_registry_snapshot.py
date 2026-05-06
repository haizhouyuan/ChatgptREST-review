import inspect
import json
from pathlib import Path

from chatgpt_web_mcp import _tools_impl


def _snapshot_tools() -> list[dict]:
    records: list[dict] = []
    for meta, fn in _tools_impl._iter_mcp_tools():
        name = (meta.get("name") or fn.__name__).strip()
        sig = inspect.signature(fn)
        params: list[str] = []
        required_params: list[str] = []
        for p in sig.parameters.values():
            # `ctx` is MCP-injected and intentionally excluded from the public contract.
            if p.name in {"ctx", "context"}:
                continue
            if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                raise AssertionError(f"{name}: variadic parameters are not allowed")
            params.append(p.name)
            if p.default is inspect._empty:
                required_params.append(p.name)
        records.append(
            {
                "name": name,
                "structured_output": bool(meta.get("structured_output")),
                "params": params,
                "required_params": required_params,
            }
        )

    records.sort(key=lambda r: r["name"])
    return records


def test_mcp_tool_registry_snapshot() -> None:
    snap_path = Path(__file__).parent / "fixtures" / "mcp_tools_snapshot.json"
    expected = json.loads(snap_path.read_text(encoding="utf-8"))
    actual = _snapshot_tools()
    assert actual == expected
