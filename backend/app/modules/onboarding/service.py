"""Client onboarding: the 13-step workflow (product owner's spec and mockups, 2026-10-19).

Who may do what
- run the workflow (questionnaire, access requests/receipts, KPIs, team, review,
  completion): the client's own Account Manager, or Super Admin
  (`onboarding.manage` + ownership);
- verify / reject platform access: `onboarding.access_verify` (AM, PM, Team Lead);
- record the client's KPI confirmation: `onboarding.kpi_confirm` (AM);
- kickoffs are meetings (app.modules.meetings): a completed `kickoff` meeting is
  step 9, a completed `internal` meeting plus an assigned team is step 10;
- everyone who can see the client can follow onboarding (read-only).

Rules
- the client cannot complete onboarding until every required access item is
  verified and every KPI target is client-confirmed (and steps 1–11 are done);
- each step updates the overall progress; completion makes the client Active and
  enables project creation; a client on hold can't progress until reactivated;
- access can only be verified or rejected once received; a rejected item blocks
  onboarding until it's received again;
- the questionnaire link is single-use, valid 30 days, stored hashed; the client
  can save a draft through it; staff can also record the answers;
- the people who must act are notified (bell): the AM when the client submits the
  questionnaire or access is rejected, the team when access arrives, new team
  members, the team on completion;
- every action is audited and appears on the client's activity timeline.

TODO(pilot-port): confirm against services/onboarding.ts and docs/onboarding-workflow.md.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import (
    MEETINGS_MANAGE,
    ONBOARDING_ACCESS_VERIFY,
    ONBOARDING_KPI_CONFIRM,
    ONBOARDING_MANAGE,
    PROJECTS_CREATE,
)
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import BusinessRuleViolation, Conflict, Forbidden, NotFound, ValidationFailed
from app.core.security import generate_token
from app.core.security import hash_token as hash_link
from app.modules.clients.models import Client, ClientTeamMember
from app.modules.meetings.models import Meeting
from app.modules.notifications.service import NotificationService
from app.modules.onboarding import kpis as kpi_rules
from app.modules.onboarding import questionnaire as q
from app.modules.onboarding.models import (
    ClientOnboarding,
    OnboardingAccessItem,
    OnboardingKpi,
    QuestionnaireLink,
)
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.schemas import (
    AccessDetails,
    AccessItemIn,
    AccessItemOut,
    AccessSummary,
    Answers,
    BoardRow,
    Choice,
    ClientSummary,
    CoverageOut,
    KickoffOut,
    KpiConfirmation,
    KpiIn,
    KpiNotesIn,
    KpiOut,
    KpiSummary,
    KpiUpdate,
    NextActionOut,
    OnboardingDetail,
    Permissions,
    PublicQuestionnaire,
    QuestionnaireForm,
    QuestionnaireLinkOut,
    QuestionnaireOut,
    QuickStatus,
    SectionOut,
    StageOut,
    StepOut,
    TeamMemberIn,
    TeamMemberOut,
    TeamMemberUpdate,
    UserRef,
)
from app.modules.onboarding.steps import (
    PRE_REVIEW,
    STEP_KEYS,
    AccessSnapshot,
    Evaluation,
    Snapshot,
    evaluate,
)
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import User
from app.platform.notifications.interfaces import NotificationRequest

QUESTIONNAIRE_TTL = timedelta(days=30)

#: Access status changes the workflow owner may make: target ← allowed current states.
MANAGE_TRANSITIONS: dict[str, frozenset[str]] = {
    "requested": frozenset({"pending"}),
    "received": frozenset({"pending", "requested", "rejected"}),
    "not_required": frozenset({"pending", "requested", "rejected"}),
    "pending": frozenset({"not_required"}),
}
#: Access status changes a verifier may make.
VERIFY_TRANSITIONS: dict[str, frozenset[str]] = {
    "verified": frozenset({"received"}),
    "rejected": frozenset({"received"}),
}
CHANNEL_LABELS = {
    "email": "e-mail",
    "call": "a call",
    "meeting": "a meeting",
    "whatsapp": "WhatsApp",
}
AREA_LABELS = {
    "account": "Account management",
    "project_management": "Project management",
    "seo": "SEO",
    "content": "Content",
    "design": "Design",
    "development": "Development",
    "social": "Social media",
    "analytics": "Analytics & reporting",
}
#: Areas every SEO engagement needs covered (coverage panel). TODO(confirm).
REQUIRED_AREAS = ("account", "project_management", "seo", "content")
ON_HOLD = "This client is on hold. Reactivate it to continue onboarding."


@dataclass
class Context:
    client: Client
    manager: User
    state: ClientOnboarding
    access: list[OnboardingAccessItem]
    kpis: list[OnboardingKpi]
    team: list[tuple[ClientTeamMember, User]]
    meetings: list[Meeting]
    has_project: bool

    def kickoff(self, kind: str) -> tuple[str, Meeting | None]:
        mine = [m for m in self.meetings if m.type == kind]
        done = next((m for m in reversed(mine) if m.status == "completed"), None)
        if done:
            return "done", done
        scheduled = next((m for m in mine if m.status == "scheduled"), None)
        return ("scheduled", scheduled) if scheduled else ("none", None)

    def snapshot(self) -> Snapshot:
        return Snapshot(
            contract_captured=bool(self.client.contract_start and self.client.contract_end),
            website=self.client.website,
            industry=self.client.industry,
            contact_name=self.client.contact_name,
            contact_email=self.client.contact_email,
            contact_phone=self.client.contact_phone,
            questionnaire=self.state.questionnaire,
            access=tuple(AccessSnapshot(i.label, i.status) for i in self.access),
            kpis_total=len(self.kpis),
            kpis_unconfirmed=sum(1 for k in self.kpis if k.confirmed_at is None),
            kickoff_client=self.kickoff("kickoff")[0],
            kickoff_internal=self.kickoff("internal")[0],
            team_size=len(self.team),
            reviewed=self.state.reviewed_at is not None,
            completed=self.state.completed_at is not None,
            has_project=self.has_project,
        )


async def add_access_items(
    session: AsyncSession, client_id: uuid.UUID, items: Sequence[tuple[str, str, str]]
) -> int:
    """Extend an open onboarding's access checklist (services added after creation)."""
    return await OnboardingRepository(session).add_access_items(client_id, items)


def _ref(user: User | None) -> UserRef | None:
    return UserRef(id=user.id, full_name=user.full_name) if user else None


def _form(answers: dict[str, Any]) -> QuestionnaireForm:
    gaps = q.missing_by_section(answers)
    return QuestionnaireForm(
        sections=[
            SectionOut(
                key=key, label=label, question=question, complete=not gaps[key], missing=gaps[key]
            )
            for key, label, question in q.SECTIONS
        ],
        goals=[Choice(key=k, label=v) for k, v in q.GOALS],
        tones=[Choice(key=k, label=v) for k, v in q.TONES],
        answers=Answers.model_validate(q.from_legacy(answers)),
    )


class OnboardingService:
    def __init__(self, session: AsyncSession, *, clock: Clock, settings: Settings) -> None:
        self._repo = OnboardingRepository(session)
        self._clock = clock
        self._settings = settings
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)
        self._notifier = NotificationService(session)

    # ================================================================ reads

    async def board(self, actor: Actor) -> list[BoardRow]:
        clients = await self._repo.visible_clients(actor)
        ids = [client.id for client, _ in clients]
        states = await self._repo.states(ids)
        access = await self._repo.access_items_for(ids)
        kpis = await self._repo.kpi_counts(ids)
        teams = await self._repo.team_sizes(ids)
        with_project = await self._repo.clients_with_projects(ids)
        meetings = await self._repo.kickoff_meetings(ids)
        rows = []
        for client, manager in clients:
            state = states.get(client.id)
            items = access.get(client.id)
            total, unconfirmed = kpis.get(client.id, (0, 0))
            ctx_meetings = meetings.get(client.id, [])
            kick = {
                kind: (
                    "done"
                    if any(m.type == kind and m.status == "completed" for m in ctx_meetings)
                    else "scheduled"
                    if any(m.type == kind for m in ctx_meetings)
                    else "none"
                )
                for kind in ("kickoff", "internal")
            }
            fields: dict[str, Any] = {
                "contract_captured": bool(client.contract_start and client.contract_end),
                "website": client.website,
                "industry": client.industry,
                "contact_name": client.contact_name,
                "contact_email": client.contact_email,
                "contact_phone": client.contact_phone,
                "kpis_total": total,
                "kpis_unconfirmed": unconfirmed,
                "team_size": teams.get(client.id, 0),
                "has_project": client.id in with_project,
                "kickoff_client": kick["kickoff"],
                "kickoff_internal": kick["internal"],
            }
            if state is not None:  # no row yet = nothing started (lazy creation)
                fields |= {
                    "questionnaire": state.questionnaire,
                    "reviewed": state.reviewed_at is not None,
                    "completed": state.completed_at is not None,
                }
            if items:
                fields["access"] = tuple(AccessSnapshot(i.label, i.status) for i in items)
            result = evaluate(Snapshot(**fields))
            nxt = result.next_step
            rows.append(
                BoardRow(
                    client_id=client.id,
                    client_name=client.name,
                    client_code=client.code,
                    client_status=client.status,  # type: ignore[arg-type]
                    status=result.status,
                    progress=result.progress,
                    current_step=nxt.label if nxt else None,
                    current_detail=(nxt.detail or None) if nxt else None,
                    account_manager=UserRef(id=manager.id, full_name=manager.full_name),
                )
            )
        rows.sort(key=lambda r: (r.status == "completed", r.client_name.lower()))
        return rows

    async def detail(self, actor: Actor, client_id: uuid.UUID) -> OnboardingDetail:
        return await self._detail(actor, await self._load(actor, client_id))

    async def team_options(self, actor: Actor, client_id: uuid.UUID) -> list[UserRef]:
        ctx = await self._load(actor, client_id)
        self._require_manage(actor, ctx)
        on_team = {u.id for _, u in ctx.team}
        return [
            UserRef(id=u.id, full_name=u.full_name)
            for u in await self._repo.team_options()
            if u.id not in on_team
        ]

    # ================================================================ steps 4–5: questionnaire

    async def send_questionnaire(self, actor: Actor, client_id: uuid.UUID) -> QuestionnaireLinkOut:
        ctx = await self._open_for_manager(actor, client_id)
        if ctx.state.questionnaire == "submitted":
            raise BusinessRuleViolation("The client has already submitted the questionnaire.")
        now = self._clock.now()
        await self._repo.expire_links(ctx.client.id, now)
        raw = generate_token()
        expires = now + QUESTIONNAIRE_TTL
        self._repo.add(
            QuestionnaireLink(
                client_id=ctx.client.id,
                token_hash=hash_link(raw),
                expires_at=expires,
                created_by_id=actor.user_id,
            )
        )
        ctx.state.questionnaire = "sent"
        ctx.state.questionnaire_sent_at = now
        await self._log(
            actor, ctx, "onboarding.questionnaire_sent", "Onboarding questionnaire link sent"
        )
        return QuestionnaireLinkOut(
            url=f"{self._settings.app_base_url.rstrip('/')}/q/{raw}",
            expires_at=expires,
            onboarding=await self._detail(actor, ctx),
        )

    async def save_answers(
        self, actor: Actor, client_id: uuid.UUID, answers: Answers, *, submit: bool
    ) -> OnboardingDetail:
        """Staff fill the questionnaire with the client (draft) or record it (submit)."""
        ctx = await self._open_for_manager(actor, client_id)
        if ctx.state.questionnaire == "submitted":
            raise BusinessRuleViolation("The questionnaire is already submitted.")
        data = answers.model_dump(mode="json")
        now = self._clock.now()
        ctx.state.questionnaire_answers = data
        ctx.state.questionnaire_updated_at = now
        if submit:
            self._require_complete(data)
            if ctx.state.questionnaire == "none":
                ctx.state.questionnaire_sent_at = now
            ctx.state.questionnaire = "submitted"
            ctx.state.questionnaire_submitted_at = now
            ctx.state.questionnaire_source = "staff"
            await self._repo.expire_links(ctx.client.id, now)
            await self._log(
                actor,
                ctx,
                "onboarding.questionnaire_recorded",
                "Questionnaire answers recorded by the team",
            )
        else:
            await self._repo.flush()
        return await self._detail(actor, ctx)

    async def public_questionnaire(self, raw_token: str) -> PublicQuestionnaire:
        link = await self._usable_link(raw_token)
        client = await self._repo.client(link.client_id)
        state = await self._repo.state(link.client_id)
        form = _form(state.questionnaire_answers or {})
        return PublicQuestionnaire(client_name=client.name, **form.model_dump())

    async def save_public_draft(self, raw_token: str, answers: Answers) -> PublicQuestionnaire:
        link = await self._usable_link(raw_token)
        state = await self._repo.state(link.client_id, lock=True)
        if state.questionnaire == "submitted":
            raise NotFound("This questionnaire has already been submitted.")
        state.questionnaire_answers = answers.model_dump(mode="json")
        state.questionnaire_updated_at = self._clock.now()
        await self._repo.flush()
        return await self.public_questionnaire(raw_token)

    async def submit_public_questionnaire(self, raw_token: str, answers: Answers) -> None:
        link = await self._usable_link(raw_token, lock=True)
        state = await self._repo.state(link.client_id, lock=True)
        if state.completed_at is not None or state.questionnaire == "submitted":
            raise NotFound("This questionnaire has already been submitted.")
        data = answers.model_dump(mode="json")
        self._require_complete(data)
        now = self._clock.now()
        state.questionnaire_answers = data
        state.questionnaire = "submitted"
        state.questionnaire_submitted_at = now
        state.questionnaire_updated_at = now
        state.questionnaire_source = "client"
        link.used_at = now
        client = await self._repo.client(link.client_id)
        await self._audit.record(
            action="onboarding.questionnaire_submitted",
            entity_type="client",
            entity_id=link.client_id,
            context={"via": "public_link"},
        )
        await self._activity.record(
            verb="questionnaire_submitted",
            subject_type="client",
            subject_id=link.client_id,
            summary=f"Questionnaire submitted by {client.contact_name or 'the client'}",
        )
        await self._notifier.notify(
            NotificationRequest(
                user_id=client.account_manager_id,
                kind="onboarding.questionnaire_submitted",
                title=f"{client.name} submitted the onboarding questionnaire",
                body="Review the answers, then collect platform access.",
                link=f"/clients/{client.id}/questionnaire",
                entity_type="client",
                entity_id=str(client.id),
            )
        )

    # ================================================================ steps 6–7: access

    async def update_access(
        self, actor: Actor, client_id: uuid.UUID, key: str, status: str
    ) -> OnboardingDetail:
        ctx = await self._load(actor, client_id, lock=True)
        self._require_open(ctx)
        item = self._access_item(ctx, key)
        if status in VERIFY_TRANSITIONS:
            if not actor.can(ONBOARDING_ACCESS_VERIFY):
                raise Forbidden("Only authorised team members may verify access.")
            if item.status not in VERIFY_TRANSITIONS[status]:
                raise BusinessRuleViolation(
                    "Access must be marked as received before it can be verified or rejected."
                )
        elif status in MANAGE_TRANSITIONS:
            self._require_manage(actor, ctx)
            if item.status not in MANAGE_TRANSITIONS[status]:
                raise BusinessRuleViolation(
                    f"{item.label} can't go from {item.status.replace('_', ' ')} to "
                    f"{status.replace('_', ' ')}."
                )
        else:
            raise ValidationFailed(f"Unknown access status '{status}'.")

        previous = item.status
        now = self._clock.now()
        self._set_access(item, status, actor, now)
        summary = (
            f"Access verified (manual): {item.label}"
            if status == "verified"
            else f"{item.label} access {status.replace('_', ' ')}"
        )
        await self._log(
            actor, ctx, "onboarding.access_updated", summary, changes={key: [previous, status]}
        )
        if status == "received":
            await self._notify_team(
                actor,
                ctx,
                "onboarding.access_received",
                f"{ctx.client.name}: {item.label} access received — please verify",
                "access",
            )
        elif status == "rejected":
            await self._notify_manager(
                actor,
                ctx,
                "onboarding.access_rejected",
                f"{ctx.client.name}: {item.label} access was rejected",
                "access",
            )
        return await self._detail(actor, ctx)

    async def bulk_access(
        self, actor: Actor, client_id: uuid.UUID, status: str
    ) -> OnboardingDetail:
        """Request every pending item, or mark every pending/requested item received."""
        ctx = await self._open_for_manager(actor, client_id)
        allowed = {"requested": {"pending"}, "received": {"pending", "requested"}}[status]
        changed = [i for i in ctx.access if i.status in allowed]
        if not changed:
            raise BusinessRuleViolation(
                "Nothing is waiting to be requested."
                if status == "requested"
                else "Nothing is waiting to be received."
            )
        now = self._clock.now()
        for item in changed:
            self._set_access(item, status, actor, now)
        verb = "requested" if status == "requested" else "marked as received"
        await self._log(
            actor,
            ctx,
            "onboarding.access_updated",
            f"Platform access {verb}: {', '.join(i.label for i in changed)}",
            changes={i.key: status for i in changed},
        )
        if status == "received":
            await self._notify_team(
                actor,
                ctx,
                "onboarding.access_received",
                f"{ctx.client.name}: platform access received — please verify",
                "access",
            )
        return await self._detail(actor, ctx)

    async def add_access_item(
        self, actor: Actor, client_id: uuid.UUID, data: AccessItemIn
    ) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        key = re.sub(r"[^A-Z0-9]+", "_", data.label.upper()).strip("_")[:20] or "ITEM"
        if any(i.key == key or i.label.lower() == data.label.lower() for i in ctx.access):
            raise Conflict(f"{data.label} is already on the checklist.")
        item = OnboardingAccessItem(
            client_id=ctx.client.id,
            key=key,
            label=data.label,
            description=data.description,
            position=max((i.position for i in ctx.access), default=0) + 1,
            is_custom=True,
        )
        self._repo.add(item)
        await self._repo.flush()
        ctx.access.append(item)
        await self._log(actor, ctx, "onboarding.access_added", f"Access item added: {data.label}")
        return await self._detail(actor, ctx)

    async def update_access_details(
        self, actor: Actor, client_id: uuid.UUID, key: str, data: AccessDetails
    ) -> OnboardingDetail:
        """Notes (and descriptions) stay editable by the AM and verifiers."""
        ctx = await self._load(actor, client_id, lock=True)
        if not (self._can_manage(actor, ctx) or actor.can(ONBOARDING_ACCESS_VERIFY)):
            raise Forbidden("Only the Account Manager or a verifier can add notes.")
        item = self._access_item(ctx, key)
        for name, value in data.model_dump(exclude_unset=True).items():
            setattr(item, name, value)
        await self._repo.flush()
        return await self._detail(actor, ctx)

    async def delete_access_item(
        self, actor: Actor, client_id: uuid.UUID, key: str
    ) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        item = self._access_item(ctx, key)
        if not item.is_custom:
            raise BusinessRuleViolation(
                "Default access items can't be removed. Mark them as not required instead."
            )
        if item.status == "verified":
            raise BusinessRuleViolation("Verified access can't be removed.")
        await self._repo.delete_access_item(item)
        ctx.access.remove(item)
        await self._log(
            actor, ctx, "onboarding.access_removed", f"Access item removed: {item.label}"
        )
        return await self._detail(actor, ctx)

    # ================================================================ step 8: KPIs

    async def add_kpi(self, actor: Actor, client_id: uuid.UUID, data: KpiIn) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        kpi = OnboardingKpi(
            client_id=ctx.client.id,
            metric=data.metric,
            description=data.description,
            baseline=data.baseline,
            target=data.target,
            unit=data.unit,
            target_date=data.target_date,
            current_value=data.current_value,
            current_updated_at=self._clock.now() if data.current_value is not None else None,
            created_by_id=actor.user_id,
        )
        self._repo.add(kpi)
        await self._repo.flush()
        ctx.kpis.append(kpi)
        await self._log(actor, ctx, "onboarding.kpi_added", f"KPI target defined: {data.metric}")
        return await self._detail(actor, ctx)

    async def update_kpi(
        self, actor: Actor, client_id: uuid.UUID, kpi_id: uuid.UUID, data: KpiUpdate
    ) -> OnboardingDetail:
        """Targets change only while onboarding is open (and then need re-confirmation);
        the current value can be updated at any time to track progress."""
        ctx = await self._load(actor, client_id, lock=True)
        self._require_manage(actor, ctx)
        kpi = self._kpi(ctx, kpi_id)
        incoming = data.model_dump(exclude_unset=True)
        for required in ("metric", "baseline", "target", "unit"):
            if required in incoming and incoming[required] is None:
                raise ValidationFailed(f"The KPI {required} can't be empty.")
        definition = {k: v for k, v in incoming.items() if k != "current_value"}
        if definition:
            self._require_open(ctx)
        changed_target = any(
            getattr(kpi, k) != v
            for k, v in definition.items()
            if k in ("baseline", "target", "target_date", "unit")
        )
        for name, value in incoming.items():
            setattr(kpi, name, value)
        if "current_value" in incoming:
            kpi.current_updated_at = self._clock.now()
        if changed_target and kpi.confirmed_at is not None:
            kpi.confirmed_at = kpi.confirmed_by_name = kpi.confirmed_via = None
        await self._repo.flush()
        summary = f"KPI updated: {kpi.metric}" + (
            " (needs the client's confirmation again)" if changed_target else ""
        )
        await self._log(actor, ctx, "onboarding.kpi_updated", summary)
        return await self._detail(actor, ctx)

    async def delete_kpi(
        self, actor: Actor, client_id: uuid.UUID, kpi_id: uuid.UUID
    ) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        kpi = self._kpi(ctx, kpi_id)
        if kpi.confirmed_at is not None:
            raise BusinessRuleViolation("A KPI the client has confirmed can't be removed.")
        await self._repo.delete_kpi(kpi)
        ctx.kpis.remove(kpi)
        await self._log(actor, ctx, "onboarding.kpi_removed", f"KPI target removed: {kpi.metric}")
        return await self._detail(actor, ctx)

    async def confirm_kpis(
        self, actor: Actor, client_id: uuid.UUID, data: KpiConfirmation
    ) -> OnboardingDetail:
        ctx = await self._load(actor, client_id, lock=True)
        self._require_open(ctx)
        if not actor.can(ONBOARDING_KPI_CONFIRM):
            raise Forbidden("Only Account Managers record client confirmations.")
        open_kpis = [k for k in ctx.kpis if k.confirmed_at is None]
        if not open_kpis:
            raise BusinessRuleViolation("There are no KPI targets waiting for confirmation.")
        now = self._clock.now()
        for kpi in open_kpis:
            kpi.confirmed_by_name = data.confirmed_by
            kpi.confirmed_via = data.via
            kpi.confirmed_at = now
        await self._log(
            actor,
            ctx,
            "onboarding.kpis_confirmed",
            f"{data.confirmed_by} confirmed the KPI targets via {CHANNEL_LABELS[data.via]}",
            context={"confirmed_by": data.confirmed_by, "via": data.via, "count": len(open_kpis)},
        )
        return await self._detail(actor, ctx)

    async def kpi_notes(
        self, actor: Actor, client_id: uuid.UUID, data: KpiNotesIn
    ) -> OnboardingDetail:
        ctx = await self._load(actor, client_id, lock=True)
        self._require_manage(actor, ctx)
        ctx.state.kpi_notes = data.notes
        ctx.state.kpi_notes_by_id = actor.user_id
        ctx.state.kpi_notes_at = self._clock.now()
        await self._repo.flush()
        return await self._detail(actor, ctx)

    # ================================================================ step 10: team

    async def add_team_member(
        self, actor: Actor, client_id: uuid.UUID, data: TeamMemberIn
    ) -> OnboardingDetail:
        ctx = await self._load(actor, client_id, lock=True)
        self._require_manage(actor, ctx)
        self._require_not_on_hold(ctx)
        if any(u.id == data.user_id for _, u in ctx.team):
            raise Conflict("This person is already on the team.")
        user = await self._repo.team_candidate(data.user_id)
        if user is None:
            raise ValidationFailed("Choose an active team member.")
        member = ClientTeamMember(
            client_id=ctx.client.id,
            user_id=user.id,
            added_by_id=actor.user_id,
            area=data.area,
            role_title=data.role_title,
            responsibilities=data.responsibilities,
            allocation=data.allocation,
        )
        self._repo.add(member)
        await self._repo.flush()
        ctx.team.append((member, user))
        role = f" as {data.role_title}" if data.role_title else ""
        await self._log(
            actor,
            ctx,
            "onboarding.team_added",
            f"{user.full_name} assigned to the client team{role}",
        )
        if user.id != actor.user_id:
            await self._notifier.notify(
                NotificationRequest(
                    user_id=user.id,
                    kind="client.team_assigned",
                    title=f"You've been added to the {ctx.client.name} team{role}",
                    link=f"/clients/{ctx.client.id}/team",
                    entity_type="client",
                    entity_id=str(ctx.client.id),
                )
            )
        return await self._detail(actor, ctx)

    async def update_team_member(
        self, actor: Actor, client_id: uuid.UUID, user_id: uuid.UUID, data: TeamMemberUpdate
    ) -> OnboardingDetail:
        ctx = await self._load(actor, client_id, lock=True)
        self._require_manage(actor, ctx)
        member = next((m for m, u in ctx.team if u.id == user_id), None)
        if member is None:
            raise NotFound("This person isn't on the team.")
        for name, value in data.model_dump(exclude_unset=True).items():
            setattr(member, name, value)
        await self._repo.flush()
        return await self._detail(actor, ctx)

    async def remove_team_member(
        self, actor: Actor, client_id: uuid.UUID, user_id: uuid.UUID
    ) -> OnboardingDetail:
        ctx = await self._load(actor, client_id, lock=True)
        self._require_manage(actor, ctx)
        entry = next(((m, u) for m, u in ctx.team if u.id == user_id), None)
        if entry is None or not await self._repo.remove_team_member(ctx.client.id, user_id):
            raise NotFound("This person isn't on the team.")
        ctx.team.remove(entry)
        await self._log(
            actor,
            ctx,
            "onboarding.team_removed",
            f"{entry[1].full_name} removed from the client team",
        )
        return await self._detail(actor, ctx)

    # ============================================================ steps 11–12: review, completion

    async def review(self, actor: Actor, client_id: uuid.UUID) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        if ctx.state.reviewed_at is not None:
            raise BusinessRuleViolation("The onboarding review has already passed.")
        incomplete = evaluate(ctx.snapshot()).incomplete(PRE_REVIEW)
        if incomplete:
            raise BusinessRuleViolation(
                f"Review can't pass yet. Incomplete: {', '.join(incomplete)}.",
                details={"incomplete": incomplete},
            )
        ctx.state.reviewed_at = self._clock.now()
        ctx.state.reviewed_by_id = actor.user_id
        await self._log(actor, ctx, "onboarding.reviewed", "Onboarding review passed")
        return await self._detail(actor, ctx)

    async def complete(self, actor: Actor, client_id: uuid.UUID) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        result = evaluate(ctx.snapshot())
        if result.state("access_ok") != "done":
            raise BusinessRuleViolation(
                "All required access items must be verified before onboarding can be completed."
            )
        if result.state("kpi") != "done":
            raise BusinessRuleViolation(
                "KPI targets require client confirmation before onboarding can be completed."
            )
        incomplete = result.incomplete(STEP_KEYS[:11])
        if incomplete:
            raise BusinessRuleViolation(
                f"Can't complete onboarding. Incomplete: {', '.join(incomplete)}.",
                details={"incomplete": incomplete},
            )
        ctx.state.completed_at = self._clock.now()
        ctx.state.completed_by_id = actor.user_id
        if ctx.client.status == "onboarding":
            ctx.client.status = "active"
        await self._log(
            actor, ctx, "onboarding.completed", "Onboarding completed — the client is now Active"
        )
        await self._notify_team(
            actor,
            ctx,
            "onboarding.completed",
            f"{ctx.client.name} is onboarded — project creation is open",
            "",
        )
        return await self._detail(actor, ctx)

    # ================================================================ reminders (job)

    async def remind_overdue(self) -> dict[str, int]:
        """Daily: tell each onboarding client's AM about the most overdue next step
        (at most one reminder per client per day)."""
        now = self._clock.now()
        sent = checked = 0
        for client, manager in await self._repo.onboarding_clients():
            checked += 1
            ctx = await self._context(client, manager)
            result = evaluate(ctx.snapshot())
            overdue = [
                a
                for a in result.next_actions(client.created_at.date(), now.date(), limit=13)
                if a.due < now.date()
            ]
            if not overdue:
                continue
            first = overdue[0]
            more = f" (+{len(overdue) - 1} more overdue)" if len(overdue) > 1 else ""
            if await self._notifier.notify_once_a_day(
                NotificationRequest(
                    user_id=client.account_manager_id,
                    kind="onboarding.overdue",
                    title=f"{client.name}: {first.title} is overdue{more}",
                    body=f"Due {first.due:%d %b %Y}. {first.detail}".strip(),
                    link=f"/clients/{client.id}",
                    entity_type="client",
                    entity_id=str(client.id),
                ),
                now,
            ):
                sent += 1
        return {"checked": checked, "reminders": sent}

    # ================================================================ helpers

    async def _load(self, actor: Actor, client_id: uuid.UUID, *, lock: bool = False) -> Context:
        found = await self._repo.visible_client(actor, client_id)
        if found is None:
            raise NotFound("This client doesn't exist or you don't have access to it.")
        client, manager = found
        return await self._context(client, manager, lock=lock)

    async def _context(self, client: Client, manager: User, *, lock: bool = False) -> Context:
        state = await self._repo.state(client.id, lock=lock)
        return Context(
            client=client,
            manager=manager,
            state=state,
            access=await self._repo.access_items(client.id),
            kpis=await self._repo.kpis(client.id),
            team=await self._repo.team(client.id),
            meetings=(await self._repo.kickoff_meetings([client.id]))[client.id],
            has_project=bool(await self._repo.clients_with_projects([client.id])),
        )

    async def _open_for_manager(self, actor: Actor, client_id: uuid.UUID) -> Context:
        ctx = await self._load(actor, client_id, lock=True)
        self._require_manage(actor, ctx)
        self._require_open(ctx)
        return ctx

    @staticmethod
    def _can_manage(actor: Actor, ctx: Context) -> bool:
        return actor.is_super_admin or (
            actor.can(ONBOARDING_MANAGE) and ctx.client.account_manager_id == actor.user_id
        )

    def _require_manage(self, actor: Actor, ctx: Context) -> None:
        if not self._can_manage(actor, ctx):
            raise Forbidden("Only the client's Account Manager can run onboarding.")

    @staticmethod
    def _locked_reason(ctx: Context) -> str | None:
        if ctx.client.status == "on_hold":
            return ON_HOLD
        if ctx.state.completed_at is not None:
            return "Onboarding is completed."
        return None

    def _require_not_on_hold(self, ctx: Context) -> None:
        if ctx.client.status == "on_hold":
            raise BusinessRuleViolation(ON_HOLD)

    def _require_open(self, ctx: Context) -> None:
        self._require_not_on_hold(ctx)
        if ctx.state.completed_at is not None:
            raise BusinessRuleViolation("Onboarding is already completed.")

    @staticmethod
    def _require_complete(data: dict[str, Any]) -> None:
        gaps = q.missing(data)
        if gaps:
            raise ValidationFailed(
                f"Please complete the questionnaire. Missing: {'; '.join(gaps)}.",
                details={"missing": gaps},
            )

    @staticmethod
    def _access_item(ctx: Context, key: str) -> OnboardingAccessItem:
        item = next((i for i in ctx.access if i.key == key), None)
        if item is None:
            raise NotFound(f"Unknown access item '{key}'.")
        return item

    @staticmethod
    def _kpi(ctx: Context, kpi_id: uuid.UUID) -> OnboardingKpi:
        kpi = next((k for k in ctx.kpis if k.id == kpi_id), None)
        if kpi is None:
            raise NotFound("KPI target not found.")
        return kpi

    @staticmethod
    def _set_access(item: OnboardingAccessItem, status: str, actor: Actor, now: Any) -> None:
        item.status = status
        if status == "requested":
            item.requested_at = now
        if status == "received":
            item.requested_at = item.requested_at or now
            item.received_at = now
        item.verified_by_id = actor.user_id if status == "verified" else None
        item.verified_at = now if status == "verified" else None

    async def _usable_link(self, raw_token: str, *, lock: bool = False) -> QuestionnaireLink:
        link = await self._repo.usable_link(raw_token, self._clock.now(), lock=lock)
        if link is None:
            raise NotFound("This questionnaire link is invalid, already used or has expired.")
        return link

    async def _notify_manager(
        self, actor: Actor, ctx: Context, kind: str, title: str, tab: str
    ) -> None:
        await self._notifier.notify_many(
            [ctx.client.account_manager_id],
            self._request(ctx, kind, title, tab),
            exclude=actor.user_id,
        )

    async def _notify_team(
        self, actor: Actor, ctx: Context, kind: str, title: str, tab: str
    ) -> None:
        await self._notifier.notify_many(
            [ctx.client.account_manager_id, *(u.id for _, u in ctx.team)],
            self._request(ctx, kind, title, tab),
            exclude=actor.user_id,
        )

    @staticmethod
    def _request(ctx: Context, kind: str, title: str, tab: str) -> NotificationRequest:
        return NotificationRequest(
            user_id=ctx.client.account_manager_id,
            kind=kind,
            title=title,
            link=f"/clients/{ctx.client.id}" + (f"/{tab}" if tab else ""),
            entity_type="client",
            entity_id=str(ctx.client.id),
        )

    async def _log(
        self,
        actor: Actor,
        ctx: Context,
        action: str,
        summary: str,
        *,
        changes: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        await self._audit.record(
            action=action,
            entity_type="client",
            entity_id=ctx.client.id,
            actor_user_id=actor.user_id,
            changes=changes,
            context=context,
        )
        await self._activity.record(
            verb=action.removeprefix("onboarding."),
            subject_type="client",
            subject_id=ctx.client.id,
            actor_user_id=actor.user_id,
            summary=summary,
        )

    async def _detail(self, actor: Actor, ctx: Context) -> OnboardingDetail:
        await self._repo.flush()
        result: Evaluation = evaluate(ctx.snapshot())
        now = self._clock.now()
        state = ctx.state
        users = await self._repo.users(
            [i.verified_by_id for i in ctx.access] + [state.kpi_notes_by_id]
        )
        roles = await self._repo.role_names([u.id for _, u in ctx.team])
        documents, contracts = await self._repo.document_counts(ctx.client.id)
        locked = self._locked_reason(ctx)
        open_ = locked is None

        # Questionnaire
        answers = state.questionnaire_answers or {}
        form = _form(answers)
        questionnaire = QuestionnaireOut(
            **form.model_dump(),
            status=state.questionnaire,  # type: ignore[arg-type]  # DB check constraint
            sent_at=state.questionnaire_sent_at,
            submitted_at=state.questionnaire_submitted_at,
            source=state.questionnaire_source,  # type: ignore[arg-type]
            updated_at=state.questionnaire_updated_at,
        )

        # Access
        required = [i for i in ctx.access if i.status != "not_required"]
        verified = sum(1 for i in required if i.status == "verified")

        # KPIs
        today = now.date()
        kpi_rows = []
        for k in ctx.kpis:
            pct = kpi_rules.progress(k.baseline, k.target, k.current_value)
            start = (k.confirmed_at or k.created_at).date()
            kpi_rows.append(
                KpiOut(
                    id=k.id,
                    metric=k.metric,
                    description=k.description,
                    baseline=k.baseline,
                    target=k.target,
                    unit=k.unit,
                    target_date=k.target_date,
                    current_value=k.current_value,
                    progress=pct,
                    status=kpi_rules.status(pct, start, k.target_date, today),
                    confirmed_by_name=k.confirmed_by_name,
                    confirmed_via=k.confirmed_via,
                    confirmed_at=k.confirmed_at,
                )
            )
        measured = [k.progress for k in kpi_rows if k.progress is not None]
        all_confirmed = bool(ctx.kpis) and all(k.confirmed_at for k in ctx.kpis)
        last = max(ctx.kpis, key=lambda k: k.confirmed_at or now) if all_confirmed else None
        kpi_summary = KpiSummary(
            total=len(kpi_rows),
            on_track=sum(1 for k in kpi_rows if k.status == "on_track"),
            at_risk=sum(1 for k in kpi_rows if k.status == "at_risk"),
            behind=sum(1 for k in kpi_rows if k.status == "behind"),
            achieved=sum(1 for k in kpi_rows if k.status == "achieved"),
            not_measured=sum(1 for k in kpi_rows if k.status == "not_measured"),
            overall=round(sum(measured) / len(measured)) if measured else None,
            notes=state.kpi_notes,
            notes_by=_ref(users.get(state.kpi_notes_by_id) if state.kpi_notes_by_id else None),
            notes_at=state.kpi_notes_at,
            confirmed_by=last.confirmed_by_name if last else None,
            confirmed_via=last.confirmed_via if last else None,
            confirmed_at=last.confirmed_at if last else None,
        )

        # Kickoffs (meetings)
        def kickoff(kind: str) -> KickoffOut:
            kick_state, meeting = ctx.kickoff(kind)
            return KickoffOut(
                state=kick_state,  # type: ignore[arg-type]
                meeting_id=meeting.id if meeting else None,
                at=meeting.starts_at if meeting else None,
            )

        # Team and coverage
        team = [
            TeamMemberOut(
                user=UserRef(id=u.id, full_name=u.full_name),
                email=u.email,
                role=roles.get(u.id),
                area=m.area,  # type: ignore[arg-type]
                role_title=m.role_title,
                responsibilities=m.responsibilities,
                allocation=m.allocation,
                added_at=m.added_at,
            )
            for m, u in ctx.team
        ]
        coverage = [
            CoverageOut(
                area=area,  # type: ignore[arg-type]
                label=label,
                members=[t.user for t in team if t.area == area]
                + (
                    [UserRef(id=ctx.manager.id, full_name=ctx.manager.full_name)]
                    if area == "account" and not any(t.area == "account" for t in team)
                    else []
                ),
                required=area in REQUIRED_AREAS,
            )
            for area, label in AREA_LABELS.items()
        ]

        # Quick status (dashboard)
        def quick(key: str, label: str, steps: tuple[str, ...]) -> QuickStatus:
            states = [result.state(s) for s in steps]
            value = (
                "completed"
                if all(s == "done" for s in states)
                else "blocked"
                if "blocked" in states
                else "in_progress"
                if any(s in ("done", "progress") for s in states)
                else "pending"
            )
            return QuickStatus(key=key, label=label, state=value)  # type: ignore[arg-type]

        quick_status = [
            quick("questionnaire", "Questionnaire", ("q_sent", "q_done")),
            quick("access", "Access Collection", ("access_in", "access_ok")),
            quick("kpis", "KPI Targets", ("kpi",)),
            quick("kickoff", "Kickoff Meeting", ("kickoff_client",)),
            quick("internal", "Internal Kickoff", ("kickoff_internal",)),
            QuickStatus(
                key="documents",
                label="Documents",
                state="completed" if contracts else "in_progress" if documents else "pending",
            ),
        ]

        can_manage = self._can_manage(actor, ctx)
        on_team = any(u.id == actor.user_id for _, u in ctx.team)
        return OnboardingDetail(
            client=ClientSummary(
                id=ctx.client.id,
                name=ctx.client.name,
                code=ctx.client.code,
                status=ctx.client.status,  # type: ignore[arg-type]
                account_manager=UserRef(id=ctx.manager.id, full_name=ctx.manager.full_name),
                created_at=ctx.client.created_at,
            ),
            status=result.status,
            progress=result.progress,
            steps=[
                StepOut(
                    number=s.number,
                    key=s.key,
                    label=s.label,
                    hint=s.hint,
                    state=s.state,
                    detail=s.detail,
                )
                for s in result.steps
            ],
            stages=[StageOut(key=s.key, label=s.label, state=s.state) for s in result.stages],
            next_actions=[
                NextActionOut(
                    step=a.step, title=a.title, detail=a.detail, due=a.due, priority=a.priority
                )
                for a in result.next_actions(ctx.client.created_at.date(), today)
            ],
            quick_status=quick_status,
            questionnaire=questionnaire,
            access=[
                AccessItemOut(
                    key=i.key,
                    label=i.label,
                    description=i.description,
                    status=i.status,  # type: ignore[arg-type]
                    is_custom=i.is_custom,
                    requested_at=i.requested_at,
                    received_at=i.received_at,
                    verified_by=_ref(users.get(i.verified_by_id) if i.verified_by_id else None),
                    verified_at=i.verified_at,
                    notes=i.notes,
                )
                for i in ctx.access
            ],
            access_summary=AccessSummary(
                required=len(required),
                verified=verified,
                percent=round(verified / len(required) * 100) if required else 100,
            ),
            kpis=kpi_rows,
            kpi_summary=kpi_summary,
            kickoff_client=kickoff("kickoff"),
            kickoff_internal=kickoff("internal"),
            team=team,
            coverage=coverage,
            documents=documents,
            contract_documents=contracts,
            reviewed_at=state.reviewed_at,
            completed_at=state.completed_at,
            locked_reason=locked,
            permissions=Permissions(
                owner=can_manage,
                manage=can_manage and open_,
                verify_access=actor.can(ONBOARDING_ACCESS_VERIFY) and open_,
                confirm_kpis=actor.can(ONBOARDING_KPI_CONFIRM) and open_,
                schedule_meetings=(
                    can_manage
                    or actor.can(MEETINGS_MANAGE)
                    or on_team
                    or ctx.client.account_manager_id == actor.user_id
                ),
                upload_documents=(
                    can_manage
                    or on_team
                    or actor.can(PROJECTS_CREATE)
                    or ctx.client.account_manager_id == actor.user_id
                ),
            ),
        )
