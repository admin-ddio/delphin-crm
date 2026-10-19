from __future__ import annotations

import pytest

from app.modules.clients.rules import domain_of, normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme Ltd", "acme"),
        ("The Acme Company", "acme"),
        ("ACME, Inc.", "acme"),
        ("Acme & Sons Pvt. Ltd.", "acme and sons"),
        ("Acme and Sons", "acme and sons"),
        ("  Blue   Widget  Co ", "blue widget"),
        ("Coca-Cola", "coca cola"),  # "co" inside a word is not a suffix
        ("Limited Edition Labs", "edition labs"),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "example.com"),
        ("www.Example.com", "example.com"),
        ("https://www.example.com/about?x=1", "example.com"),
        ("http://shop.example.co.uk", "shop.example.co.uk"),
        ("  EXAMPLE.COM  ", "example.com"),
        ("", None),
        (None, None),
        ("not a website", None),
        ("localhost", None),
    ],
)
def test_domain_of(raw: str | None, expected: str | None) -> None:
    assert domain_of(raw) == expected
