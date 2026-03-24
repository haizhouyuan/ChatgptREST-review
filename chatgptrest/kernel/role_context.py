"""Role context — contextvars binding for the active business role.

Provides a thread-local (or async-context-local) variable that carries the
currently active RoleSpec through the call stack.  Memory writers (stage())
read this to auto-inject ``source.role``; context resolvers read it to
scope episodic/semantic queries.

Usage::

    from chatgptrest.kernel.role_context import with_role, get_current_role

    role = load_role("devops")
    with with_role(role):
        # All memory writes inside here get source.role=devops
        ...
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chatgptrest.kernel.team_types import RoleSpec

_current_role: contextvars.ContextVar["RoleSpec | None"] = contextvars.ContextVar(
    "current_agent_role", default=None,
)


@contextlib.contextmanager
def with_role(role: "RoleSpec"):
    """Context manager that sets the active role for the duration of a block."""
    token = _current_role.set(role)
    try:
        yield role
    finally:
        _current_role.reset(token)


def get_current_role() -> "RoleSpec | None":
    """Return the currently active RoleSpec, or None."""
    return _current_role.get()


def get_current_role_name() -> str:
    """Return the memory_namespace of the current role, or empty string."""
    role = _current_role.get()
    if role is None:
        return ""
    return getattr(role, "memory_namespace", "") or ""
