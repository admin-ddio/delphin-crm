"""Record-level scopes (layer 2 of authorisation).

Every list query and mutation in a module goes through apply_scope(). A scope
returns ONE boolean clause; caller filters are ANDed with it, never merged into it.

Why this matters: the pilot had a real bug where a filter containing an OR was
dict-merged into the scope's filter object. The OR replaced the scope's own
condition and widened access. Composing clauses with and_() makes that
impossible: user filters can only narrow a scope. See tests/unit/test_scopes.py.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import ColumnElement, Select, and_, true

from app.authz.actor import Actor


class Scope(Protocol):
    def clause(self, actor: Actor) -> ColumnElement[bool]:
        """The rows `actor` may see. Return sqlalchemy.true() for unrestricted."""
        ...


class Unrestricted:
    """Scope for entities with no record-level restriction (or for Super Admin paths)."""

    def clause(self, actor: Actor) -> ColumnElement[bool]:
        return true()


def combine(*clauses: ColumnElement[bool]) -> ColumnElement[bool]:
    """AND-compose clauses. The only sanctioned way to join a scope with filters."""
    if not clauses:
        return true()
    return and_(*clauses)


def apply_scope[S: Select[Any]](
    stmt: S, actor: Actor, scope: Scope, *filters: ColumnElement[bool]
) -> S:
    """Restrict `stmt` to the actor's scope, then narrow it by `filters`."""
    return stmt.where(combine(scope.clause(actor), *filters))
