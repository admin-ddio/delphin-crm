"""The onboarding questionnaire: sections, choices and completeness rules. Pure.

Seven-step wizard from the product mockups: Business Goals, Target Markets,
Competitors, Brand Voice, Past SEO Work, Additional Information, Summary. Answers
are stored as one JSON document (see schemas.Answers); drafts may be partial,
submission needs every required answer. TODO(pilot-port): confirm questions.
"""

from __future__ import annotations

from typing import Any, Final

SECTIONS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "business_goals",
        "Business Goals",
        "What are your primary business goals for the next 12 months?",
    ),
    ("target_markets", "Target Markets", "Where are your customers, and who are they?"),
    ("competitors", "Competitors", "Who do you compete with online?"),
    ("brand_voice", "Brand Voice", "How should your brand sound?"),
    ("past_seo", "Past SEO Work", "What has been done on SEO before?"),
    ("additional", "Additional Information", "Anything else we should know?"),
)

GOALS: Final[tuple[tuple[str, str], ...]] = (
    ("organic_traffic", "Increase Organic Traffic"),
    ("leads", "Generate More Leads"),
    ("sales", "Increase Sales"),
    ("brand_awareness", "Improve Brand Awareness"),
    ("reputation", "Improve Online Reputation"),
    ("keywords", "Rank for More Keywords"),
    ("new_markets", "Expand to New Markets"),
    ("engagement", "Improve User Engagement"),
    ("other", "Other"),
)
TONES: Final[tuple[tuple[str, str], ...]] = (
    ("professional", "Professional"),
    ("friendly", "Friendly"),
    ("authoritative", "Authoritative"),
    ("conversational", "Conversational"),
    ("technical", "Technical"),
    ("playful", "Playful"),
    ("inspirational", "Inspirational"),
    ("premium", "Premium"),
)
YES_NO: Final = ("yes", "no", "unsure")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def missing_by_section(answers: dict[str, Any]) -> dict[str, list[str]]:
    """Section key → the required answers still missing (empty list = complete)."""
    goals = answers.get("business_goals") or {}
    markets = answers.get("target_markets") or {}
    rivals = answers.get("competitors") or {}
    voice = answers.get("brand_voice") or {}
    past = answers.get("past_seo") or {}
    out: dict[str, list[str]] = {key: [] for key, _, _ in SECTIONS}
    if not goals.get("goals"):
        out["business_goals"].append("at least one goal")
    if "other" in (goals.get("goals") or []) and not _text(goals.get("other")):
        out["business_goals"].append("the other goal")
    if not _text(goals.get("details")):
        out["business_goals"].append("your goals in detail")
    if not _text(markets.get("locations")):
        out["target_markets"].append("target locations")
    if not _text(markets.get("audiences")):
        out["target_markets"].append("target audiences")
    if not any(_text(c.get("name")) for c in rivals.get("competitors") or []):
        out["competitors"].append("at least one competitor")
    if not voice.get("tones"):
        out["brand_voice"].append("at least one tone")
    if past.get("worked_before") not in YES_NO:
        out["past_seo"].append("whether SEO was done before")
    return out


def missing(answers: dict[str, Any]) -> list[str]:
    """Human-readable list of everything required that is still missing."""
    labels = {key: label for key, label, _ in SECTIONS}
    return [
        f"{labels[section]}: {item}"
        for section, items in missing_by_section(answers).items()
        for item in items
    ]


def from_legacy(flat: dict[str, Any]) -> dict[str, Any]:
    """The first questionnaire stored six free-text answers; map them onto sections."""
    if not flat or ("business_goals" in flat and isinstance(flat["business_goals"], dict)):
        return flat
    return {
        "business_goals": {"goals": [], "details": flat.get("business_goals")},
        "target_markets": {
            "locations": flat.get("target_markets"),
            "audiences": flat.get("target_audiences"),
        },
        "competitors": {"competitors": [], "notes": flat.get("competitors")},
        "brand_voice": {"tones": [], "guidelines": flat.get("brand_voice")},
        "past_seo": {},
        "additional": {"products_services": flat.get("products_services")},
    }
