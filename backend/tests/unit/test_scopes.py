"""Guards scope composition. Regression test for the pilot bug where an OR filter
was dict-merged into a scope and widened access."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ColumnElement, Integer, MetaData, String, Table, or_, select, true
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.sql.elements import BooleanClauseList, ClauseElement

from app.authz.actor import Actor
from app.authz.scopes import Unrestricted, apply_scope, combine

metadata = MetaData()
things = Table(
    "things",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("owner", String),
    Column("team", String),
    Column("status", String),
)

ACTOR = Actor(
    user_id=uuid.uuid4(),
    email="a@example.test",
    full_name="A",
    roles=frozenset(),
    permissions=frozenset(),
)


class OwnerOrTeamScope:
    def clause(self, actor: Actor) -> ColumnElement[bool]:
        return or_(things.c.owner == "me", things.c.team == "mine")


def _sql(stmt: ClauseElement) -> str:
    compiled = stmt.compile(dialect=PGDialect(), compile_kwargs={"literal_binds": True})
    return " ".join(str(compiled).split())


def test_or_filter_cannot_widen_an_or_scope() -> None:
    user_filter = or_(things.c.status == "open", things.c.status == "blocked")
    stmt = apply_scope(select(things.c.id), ACTOR, OwnerOrTeamScope(), user_filter)
    where = _sql(stmt).split(" WHERE ", 1)[1]
    assert where == (
        "(things.owner = 'me' OR things.team = 'mine') "
        "AND (things.status = 'open' OR things.status = 'blocked')"
    )


def test_filters_are_anded_not_merged() -> None:
    clause = combine(things.c.owner == "me", things.c.status == "open")
    assert isinstance(clause, BooleanClauseList)
    assert _sql(select(things.c.id).where(clause)).endswith(
        "WHERE things.owner = 'me' AND things.status = 'open'"
    )


def test_combine_without_clauses_is_true() -> None:
    assert _sql(select(things.c.id).where(combine())).endswith("WHERE true")


def test_unrestricted_scope_only_applies_filters() -> None:
    stmt = apply_scope(select(things.c.id), ACTOR, Unrestricted(), things.c.status == "open")
    assert _sql(stmt).endswith("WHERE things.status = 'open'")


def test_unrestricted_clause_is_true() -> None:
    assert Unrestricted().clause(ACTOR).compare(true())
