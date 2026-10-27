"""What each service needs from onboarding (services plan, 2026-10-27).

The catalogue itself (service types and their default task templates) lives in the
database (migration 0011) so admins can edit templates. These are the per-service
platform-access items that tailor the onboarding checklist. Pure data.
TODO(pilot-port): confirm against the pilot's onboarding access list.
"""

from __future__ import annotations

from typing import Final

#: (key, label, description); keys are unique across services.
AccessItem = tuple[str, str, str]

ALWAYS: Final[tuple[AccessItem, ...]] = (
    ("GDRIVE", "Google Drive Access", "Shared drive for documents and reports"),
)

ACCESS_BY_SERVICE: Final[dict[str, tuple[AccessItem, ...]]] = {
    "seo": (
        ("GSC", "Google Search Console", "Access to GSC for domain performance data"),
        ("GA4", "Google Analytics 4", "GA4 access for traffic and conversion tracking"),
        ("CMS", "CMS Access", "Admin/editor access to the website CMS"),
        ("AHREFS", "Ahrefs Account", "Access to Ahrefs for SEO analysis"),
    ),
    "social_media": (
        ("META_BS", "Meta Business Suite", "Admin access to the Meta Business portfolio"),
        ("INSTAGRAM", "Instagram Account", "Professional account access or collaborator role"),
        ("FB_PAGE", "Facebook Page", "Page admin or editor role"),
        ("LINKEDIN", "LinkedIn Page", "Super admin or content admin of the company page"),
    ),
    "website": (
        ("DOMAIN_DNS", "Domain & DNS", "Registrar or DNS access for the website domain"),
        ("HOSTING", "Hosting / Server", "Hosting control panel or server access"),
        ("CMS", "CMS Access", "Admin/editor access to the website CMS"),
        ("GA4", "Google Analytics 4", "GA4 access for traffic and conversion tracking"),
    ),
    "web_app": (
        ("CLOUD", "Cloud Hosting", "Access to the cloud account (AWS, GCP, Azure…)"),
        ("REPO", "Code Repository", "Access to the code repository (GitHub, GitLab…)"),
        ("DOMAIN_DNS", "Domain & DNS", "Registrar or DNS access for the application domain"),
    ),
    "mobile_app": (
        ("APPLE_DEV", "Apple Developer Account", "App Store Connect access (Admin or App Manager)"),
        ("PLAY_CONSOLE", "Google Play Console", "Play Console access to the developer account"),
        ("FIREBASE", "Firebase Project", "Access to the app's Firebase project"),
        ("REPO", "Code Repository", "Access to the code repository (GitHub, GitLab…)"),
    ),
}


def access_items_for(service_keys: list[str]) -> tuple[AccessItem, ...]:
    """The union of the services' access items (first label wins), then the common ones."""
    seen: dict[str, AccessItem] = {}
    for key in service_keys:
        for item in ACCESS_BY_SERVICE.get(key, ()):
            seen.setdefault(item[0], item)
    for item in ALWAYS:
        seen.setdefault(item[0], item)
    return tuple(seen.values())
