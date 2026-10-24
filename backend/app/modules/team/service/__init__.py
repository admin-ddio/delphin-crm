"""Team & Employees services: sign-up approvals, the people core, and Organization &
Role Settings (reporting relationships, org chart, roles, audit log)."""

from app.modules.team.service.org import OrgService
from app.modules.team.service.people import PeopleService
from app.modules.team.service.registrations import TeamService

__all__ = ["OrgService", "PeopleService", "TeamService"]
