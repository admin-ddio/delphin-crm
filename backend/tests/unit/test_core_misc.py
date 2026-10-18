"""Config, clock, pagination, logging and DB type helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql.base import PGDialect

from app.core.clock import FixedClock, SystemClock, get_clock
from app.core.errors import ValidationFailed
from app.core.logging import configure_logging, get_logger
from app.core.pagination import Page, PageParams, page_params, parse_sort
from app.db.types import UTCDateTime, to_money
from tests.conftest import make_settings

STRONG = "0123456789abcdef0123456789abcdef0123"


class TestSettings:
    def test_csv_lists(self) -> None:
        settings = make_settings(allowed_hosts="a.test, b.test,", cors_origins="http://x.test")
        assert settings.allowed_hosts == ["a.test", "b.test"]
        assert settings.cors_origins == ["http://x.test"]

    def test_requires_async_driver(self) -> None:
        with pytest.raises(ValidationError, match="asyncpg"):
            make_settings(database_url="postgresql://u:p@h/db")

    def test_dev_defaults(self) -> None:
        settings = make_settings(app_env="development")
        assert settings.docs_enabled
        assert not settings.json_logs
        assert not settings.is_production

    def test_production_guards(self) -> None:
        ok = make_settings(app_env="production", secret_key=STRONG, cron_secret=STRONG)
        assert ok.json_logs
        assert not ok.docs_enabled
        assert make_settings(
            app_env="production", secret_key=STRONG, cron_secret=STRONG, expose_docs=True
        ).docs_enabled

        with pytest.raises(ValidationError, match="SECRET_KEY is too weak"):
            make_settings(app_env="production", secret_key="change-me-" + STRONG)
        with pytest.raises(ValidationError, match="CRON_SECRET is too weak"):
            make_settings(app_env="production", secret_key=STRONG, cron_secret="short")
        with pytest.raises(ValidationError, match="CORS_ORIGINS"):
            make_settings(app_env="production", cors_origins=["http://x.test"])
        with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
            make_settings(app_env="production", allowed_hosts=["*"])

    def test_log_level_case_insensitive(self) -> None:
        assert make_settings(log_level="debug").log_level == "DEBUG"


def test_clocks() -> None:
    assert SystemClock().now().tzinfo is UTC
    assert isinstance(get_clock(), SystemClock)
    fixed = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    fixed.advance(timedelta(days=1))
    assert fixed.now() == datetime(2026, 1, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 1, 1))  # noqa: DTZ001


class TestPagination:
    def test_params(self) -> None:
        params = page_params(page=3, page_size=20)
        assert (params.offset, params.limit) == (40, 20)
        with pytest.raises(ValidationError):
            PageParams(page=0)
        with pytest.raises(ValidationError):
            PageParams(page_size=1000)

    def test_page_envelope(self) -> None:
        page = Page[int].create([1, 2], total=7, params=PageParams(page=2, page_size=2))
        assert page.model_dump() == {"items": [1, 2], "total": 7, "page": 2, "page_size": 2}

    def test_parse_sort(self) -> None:
        assert parse_sort(None, {"name"}) == []
        assert parse_sort("name,-created_at, ,+code", {"name", "created_at", "code"}) == [
            ("name", "asc"),
            ("created_at", "desc"),
            ("code", "asc"),
        ]
        with pytest.raises(ValidationFailed):
            parse_sort("password_hash", {"name"})


def test_logging_configures_both_modes() -> None:
    configure_logging(make_settings(log_json=True))
    get_logger("test").info("json_mode")
    configure_logging(make_settings(log_json=False))
    get_logger("test").info("console_mode")


class TestDbTypes:
    def test_money(self) -> None:
        assert to_money("10.005") == Decimal("10.01")
        assert to_money(3) == Decimal("3.00")

    def test_utc_datetime(self) -> None:
        column_type = UTCDateTime()
        dialect = PGDialect()
        aware = datetime(2026, 1, 1, 12, tzinfo=UTC)
        assert column_type.process_bind_param(aware, dialect) == aware
        assert column_type.process_bind_param(None, dialect) is None
        assert column_type.process_result_value(aware, dialect) == aware
        assert column_type.process_result_value(None, dialect) is None
        with pytest.raises(ValueError, match="Naive"):
            column_type.process_bind_param(datetime(2026, 1, 1), dialect)  # noqa: DTZ001
