from __future__ import annotations

import builtins
import symtable
from pathlib import Path


_ALLOWED_IMPLICIT_GLOBALS = {
    "__annotations__",
    "__builtins__",
    "__cached__",
    "__doc__",
    "__file__",
    "__loader__",
    "__name__",
    "__package__",
    "__spec__",
}

_BUILTINS = set(dir(builtins))


def _defined_module_symbols(top: symtable.SymbolTable) -> set[str]:
    out: set[str] = set()
    for sym in top.get_symbols():
        if sym.is_imported() or sym.is_assigned() or sym.is_parameter():
            out.add(sym.get_name())
    return out


def _referenced_globals(table: symtable.SymbolTable) -> set[str]:
    out: set[str] = set()
    for sym in table.get_symbols():
        if not sym.is_referenced():
            continue
        if sym.is_global():
            out.add(sym.get_name())
    for child in table.get_children():
        out |= _referenced_globals(child)
    return out


def _missing_globals_for_module(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    top = symtable.symtable(source, str(path), "exec")
    defined = _defined_module_symbols(top)
    referenced = _referenced_globals(top)

    missing = []
    for name in sorted(referenced):
        if name in defined:
            continue
        if name in _BUILTINS:
            continue
        if name in _ALLOWED_IMPLICIT_GLOBALS:
            continue
        missing.append(name)
    return missing


def test_provider_modules_have_no_missing_globals() -> None:
    missing_by_module: dict[str, list[str]] = {}
    providers_dir = Path("chatgpt_web_mcp/providers")
    modules = sorted(p for p in providers_dir.glob("*.py") if p.name != "__init__.py")
    assert modules, "No provider modules found to scan."
    for mod in modules:
        missing = _missing_globals_for_module(mod)
        if missing:
            missing_by_module[str(mod)] = missing

    assert not missing_by_module, (
        "Provider modules reference missing globals (likely refactor leftovers).\n"
        + "\n".join(f"- {k}: {v}" for k, v in sorted(missing_by_module.items()))
    )
