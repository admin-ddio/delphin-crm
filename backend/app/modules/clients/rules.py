"""Pure rules for clients: duplicate-detection normalisation and status labels.

Ported from the clickable demo (`normName`, `domainOf`). TODO(pilot-port): diff
against services/clients.ts and its tests when the pilot source arrives.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

_LEGAL_SUFFIXES = re.compile(r"\b(the|inc|llc|ltd|limited|co|corp|company|pvt|private)\b")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]")
_SPACES = re.compile(r"\s+")
_SCHEME = re.compile(r"^https?:", re.IGNORECASE)


def normalize_name(name: str) -> str:
    """'The Acme & Sons Pvt. Ltd.' → 'acme and sons' (used for the similar-name warning)."""
    value = name.lower().replace("&", " and ")
    value = _NON_ALNUM.sub(" ", value)
    value = _LEGAL_SUFFIXES.sub(" ", value)
    return _SPACES.sub(" ", value).strip()


def domain_of(website: str | None) -> str | None:
    """'https://www.Acme.com/about' → 'acme.com'; None when there's no usable host."""
    if not website or not website.strip():
        return None
    raw = website.strip()
    if not _SCHEME.match(raw):
        raw = f"https://{raw}"
    try:
        host = urlsplit(raw).hostname
    except ValueError:
        return None
    if not host or "." not in host:
        return None
    host = host.lower()
    return host.removeprefix("www.")


STATUS_LABELS = {
    "onboarding": "Onboarding",
    "active": "Active",
    "on_hold": "On hold",
    "completed": "Completed",
}
