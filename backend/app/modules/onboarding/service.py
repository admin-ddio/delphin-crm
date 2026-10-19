"""Client onboarding: the 13-step workflow (rules from the clickable demo).

Who may do what
- run the workflow (contract, questionnaire, access received, KPIs, kickoffs,
  team, review, completion): the client's own Account Manager, or Super Admin
  (`onboarding.manage` + ownership);
- verify / reject platform access: `onboarding.access_verify` (AM, PM, Team Lead);
- record the client's KPI confirmation: `onboarding.kpi_confirm` (AM);
- everyone who can see the client can follow onboarding (read-only).

Rules
- access can only be verified or rejected once it has been received; a
  rejected item blocks onboarding until it's received again;
- the review passes only when steps 1–10 are done;
- completion re-checks: all required access verified, all KPIs client-confirmed,
  steps 1–11 done; the client then becomes Active and the workflow is locked;
- signing the contract moves the client from "Contract pending" to "Onboarding";
- the questionnaire link is single-use, valid 30 days, stored hashed; sending a
  new one invalidates the old;
- every action is audited and appears on the client's activity timeline.

TODO(pilot-port): confirm against services/onboarding.ts and docs/onboarding-workflow.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actor import Actor
from app.authz.permissions import (
    ONBOARDING_ACCESS_VERIFY,
    ONBOARDING_KPI_CONFIRM,
    ONBOARDING_MANAGE,
)
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import BusinessRuleViolation, Conflict, Forbidden, NotFound, ValidationFailed
from app.core.security import generate_token, hash_token
from app.modules.clients.models import Client, ClientTeamMember
from app.modules.onboarding.models import (
    ClientOnboarding,
    OnboardingAccessItem,
    OnboardingKpi,
    QuestionnaireLink,
)
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.schemas import (
    AccessItemOut,
    BoardRow,
    KickoffAction,
    KickoffOut,
    KpiConfirmation,
    KpiIn,
    KpiOut,
    OnboardingDetail,
    Permissions,
    PublicQuestionnaire,
    QuestionnaireLinkOut,
    QuestionOut,
    StepOut,
    UserRef,
)
from app.modules.onboarding.steps import (
    PRE_REVIEW,
    QUESTIONS,
    STEP_KEYS,
    AccessSnapshot,
    Evaluation,
    Snapshot,
    evaluate,
)
from app.platform.activity.service import ActivityRecorder
from app.platform.audit.service import AuditWriter
from app.platform.identity.models import User

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


@dataclass
class Context:
    client: Client
    manager: User
    state: ClientOnboarding
    access: list[OnboardingAccessItem]
    kpis: list[OnboardingKpi]
    team: list[User]

    def snapshot(self) -> Snapshot:
        return Snapshot(
            website=self.client.website,
            industry=self.client.industry,
            contact_name=self.client.contact_name,
            contact_email=self.client.contact_email,
            contract=self.state.contract,
            questionnaire=self.state.questionnaire,
            access=tuple(AccessSnapshot(i.label, i.status) for i in self.access),
            kpis_total=len(self.kpis),
            kpis_unconfirmed=sum(1 for k in self.kpis if k.confirmed_at is None),
            kickoff_client=self.state.kickoff_client,
            kickoff_internal=self.state.kickoff_internal,
            team_size=len(self.team),
            reviewed=self.state.reviewed_at is not None,
            completed=self.state.completed_at is not None,
            has_project=False,  # TODO: projects module
        )


def _ref(user: User) -> UserRef:
    return UserRef(id=user.id, full_name=user.full_name)


class OnboardingService:
    def __init__(self, session: AsyncSession, *, clock: Clock, settings: Settings) -> None:
        self._repo = OnboardingRepository(session)
        self._clock = clock
        self._settings = settings
        self._audit = AuditWriter(session)
        self._activity = ActivityRecorder(session)

    # ================================================================ reads

    async def board(self, actor: Actor) -> list[BoardRow]:
        clients = await self._repo.visible_clients(actor)
        ids = [client.id for client, _ in clients]
        states = await self._repo.states(ids)
        access = await self._repo.access_items_for(ids)
        kpis = await self._repo.kpi_counts(ids)
        teams = await self._repo.team_sizes(ids)
        rows = []
        for client, manager in clients:
            state = states.get(client.id)
            items = access.get(client.id)
            total, unconfirmed = kpis.get(client.id, (0, 0))
            fields: dict[str, Any] = {
                "website": client.website,
                "industry": client.industry,
                "contact_name": client.contact_name,
                "contact_email": client.contact_email,
                "kpis_total": total,
                "kpis_unconfirmed": unconfirmed,
                "team_size": teams.get(client.id, 0),
            }
            if state is not None:  # no row yet = nothing started (lazy creation)
                fields |= {
                    "contract": state.contract,
                    "questionnaire": state.questionnaire,
                    "kickoff_client": state.kickoff_client,
                    "kickoff_internal": state.kickoff_internal,
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
                    status=result.status,
                    progress=result.progress,
                    current_step=nxt.label if nxt else None,
                    current_detail=(nxt.detail or None) if nxt else None,
                    account_manager=_ref(manager),
                )
            )
        # Demo order: unfinished first, then by name.
        rows.sort(key=lambda r: (r.status == "completed", r.client_name.lower()))
        return rows

    async def detail(self, actor: Actor, client_id: uuid.UUID) -> OnboardingDetail:
        return await self._detail(actor, await self._load(actor, client_id))

    async def team_options(self, actor: Actor, client_id: uuid.UUID) -> list[UserRef]:
        ctx = await self._load(actor, client_id)
        self._require_manage(actor, ctx)
        on_team = {u.id for u in ctx.team}
        return [_ref(u) for u in await self._repo.team_options() if u.id not in on_team]

    # ================================================================ step 1: contract

    async def contract(
        self, actor: Actor, client_id: uuid.UUID, action: Literal["record", "sign"]
    ) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        if action == "record":
            if ctx.state.contract != "none":
                raise BusinessRuleViolation("The contract is already recorded.")
            ctx.state.contract = "draft"
            summary = f"Contract recorded for {ctx.client.name}"
        else:
            if ctx.state.contract != "draft":
                raise BusinessRuleViolation("Record the contract before marking it signed.")
            ctx.state.contract = "signed"
            ctx.state.contract_signed_at = self._clock.now()
            if ctx.client.status == "contract_pending":
                ctx.client.status = "onboarding"
            summary = f"Contract for {ctx.client.name} marked as signed"
        await self._log(actor, ctx, f"onboarding.contract_{action}", summary)
        return await self._detail(actor, ctx)

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
                token_hash=hash_token(raw),
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

    async def record_answers(
        self, actor: Actor, client_id: uuid.UUID, answers: dict[str, str]
    ) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        if ctx.state.questionnaire != "sent":
            raise BusinessRuleViolation("Send the questionnaire before recording answers.")
        self._accept_answers(ctx.state, answers)
        await self._repo.expire_links(ctx.client.id, self._clock.now())
        await self._log(
            actor,
            ctx,
            "onboarding.questionnaire_recorded",
            "Client's questionnaire answers recorded",
        )
        return await self._detail(actor, ctx)

    async def public_questionnaire(self, raw_token: str) -> PublicQuestionnaire:
        link = await self._usable_link(raw_token)
        client = await self._repo.client(link.client_id)
        return PublicQuestionnaire(
            client_name=client.name,
            questions=[QuestionOut(key=k, label=label, answer=None) for k, label in QUESTIONS],
        )

    async def submit_public_questionnaire(self, raw_token: str, answers: dict[str, str]) -> None:
        link = await self._usable_link(raw_token)
        state = await self._repo.state(link.client_id, lock=True)
        if state.completed_at is not None or state.questionnaire == "submitted":
            raise NotFound("This questionnaire has already been submitted.")
        self._accept_answers(state, answers)
        link.used_at = self._clock.now()
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
            summary="Client submitted the onboarding questionnaire",
        )

    # ================================================================ steps 6–7: access

    async def update_access(
        self, actor: Actor, client_id: uuid.UUID, key: str, status: str
    ) -> OnboardingDetail:
        ctx = await self._load(actor, client_id, lock=True)
        self._require_open(ctx)
        item = next((i for i in ctx.access if i.key == key), None)
        if item is None:
            raise NotFound(f"Unknown access item '{key}'.")
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
        item.status = status
        item.verified_by_id = actor.user_id if status == "verified" else None
        item.verified_at = self._clock.now() if status == "verified" else None
        summary = (
            f"Access verified (manual): {item.label}"
            if status == "verified"
            else f"{item.label} access {status.replace('_', ' ')}"
        )
        await self._log(
            actor, ctx, "onboarding.access_updated", summary, changes={key: [previous, status]}
        )
        return await self._detail(actor, ctx)

    async def receive_all(self, actor: Actor, client_id: uuid.UUID) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        changed = [i.key for i in ctx.access if i.status in ("pending", "requested")]
        if not changed:
            raise BusinessRuleViolation("Nothing is waiting to be received.")
        for item in ctx.access:
            if item.key in changed:
                item.status = "received"
        await self._log(
            actor,
            ctx,
            "onboarding.access_updated",
            "All platform access marked as received",
            changes={key: ["pending/requested", "received"] for key in changed},
        )
        return await self._detail(actor, ctx)

    # ================================================================ step 8: KPIs

    async def add_kpi(self, actor: Actor, client_id: uuid.UUID, data: KpiIn) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        kpi = OnboardingKpi(
            client_id=ctx.client.id,
            metric=data.metric,
            baseline=data.baseline,
            target=data.target,
            unit=data.unit,
            created_by_id=actor.user_id,
        )
        self._repo.add(kpi)
        await self._repo.flush()
        ctx.kpis.append(kpi)
        await self._log(actor, ctx, "onboarding.kpi_added", f"KPI target defined: {data.metric}")
        return await self._detail(actor, ctx)

    async def delete_kpi(
        self, actor: Actor, client_id: uuid.UUID, kpi_id: uuid.UUID
    ) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        kpi = next((k for k in ctx.kpis if k.id == kpi_id), None)
        if kpi is None:
            raise NotFound("KPI target not found.")
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

    # ================================================================ steps 9–10: kickoffs & team

    async def kickoff(
        self,
        actor: Actor,
        client_id: uuid.UUID,
        kind: Literal["client", "internal"],
        data: KickoffAction,
    ) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        field = f"kickoff_{kind}"
        current = getattr(ctx.state, field)
        who = "Client" if kind == "client" else "Internal"
        if data.action == "schedule":
            if current != "none":
                raise BusinessRuleViolation(f"The {who.lower()} kickoff is already scheduled.")
            setattr(ctx.state, field, "scheduled")
            setattr(ctx.state, f"{field}_at", data.at)
            summary = f"{who} kickoff scheduled"
        else:
            if current != "scheduled":
                raise BusinessRuleViolation(
                    f"Schedule the {who.lower()} kickoff before completing it."
                )
            setattr(ctx.state, field, "done")
            if data.at is not None:
                setattr(ctx.state, f"{field}_at", data.at)
            setattr(ctx.state, f"{field}_notes", data.notes)
            summary = f"{who} kickoff completed"
        await self._log(actor, ctx, f"onboarding.kickoff_{kind}_{data.action}", summary)
        return await self._detail(actor, ctx)

    async def add_team_member(
        self, actor: Actor, client_id: uuid.UUID, user_id: uuid.UUID
    ) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        if any(u.id == user_id for u in ctx.team):
            raise Conflict("This person is already on the team.")
        user = await self._repo.team_candidate(user_id)
        if user is None:
            raise ValidationFailed("Choose an active employee, team lead or project manager.")
        self._repo.add(
            ClientTeamMember(client_id=ctx.client.id, user_id=user.id, added_by_id=actor.user_id)
        )
        await self._repo.flush()
        ctx.team.append(user)
        await self._log(
            actor, ctx, "onboarding.team_added", f"{user.full_name} assigned to the client team"
        )
        return await self._detail(actor, ctx)

    async def remove_team_member(
        self, actor: Actor, client_id: uuid.UUID, user_id: uuid.UUID
    ) -> OnboardingDetail:
        ctx = await self._open_for_manager(actor, client_id)
        user = next((u for u in ctx.team if u.id == user_id), None)
        if user is None or not await self._repo.remove_team_member(ctx.client.id, user_id):
            raise NotFound("This person isn't on the team.")
        ctx.team.remove(user)
        await self._log(
            actor, ctx, "onboarding.team_removed", f"{user.full_name} removed from the client team"
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
        ctx.client.status = "active"
        await self._log(
            actor, ctx, "onboarding.completed", "Onboarding completed — the client is now Active"
        )
        return await self._detail(actor, ctx)

    # ================================================================ helpers

    async def _load(self, actor: Actor, client_id: uuid.UUID, *, lock: bool = False) -> Context:
        found = await self._repo.visible_client(actor, client_id)
        if found is None:
            raise NotFound("This client doesn't exist or you don't have access to it.")
        client, manager = found
        state = await self._repo.state(client.id, lock=lock)
        return Context(
            client=client,
            manager=manager,
            state=state,
            access=await self._repo.access_items(client.id),
            kpis=await self._repo.kpis(client.id),
            team=await self._repo.team(client.id),
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
    def _require_open(ctx: Context) -> None:
        if ctx.state.completed_at is not None:
            raise BusinessRuleViolation("Onboarding is already completed.")

    def _accept_answers(self, state: ClientOnboarding, answers: dict[str, str]) -> None:
        keys = {key for key, _ in QUESTIONS}
        unknown = set(answers) - keys
        if unknown:
            raise ValidationFailed("Unknown questions.", details={"unknown": sorted(unknown)})
        cleaned = {key: (answers.get(key) or "").strip() for key in keys}
        missing = [label for key, label in QUESTIONS if not cleaned[key]]
        if missing:
            raise ValidationFailed(
                f"Please answer every question. Missing: {', '.join(missing)}.",
                details={"missing": missing},
            )
        state.questionnaire = "submitted"
        state.questionnaire_submitted_at = self._clock.now()
        state.questionnaire_answers = cleaned

    async def _usable_link(self, raw_token: str) -> QuestionnaireLink:
        link = await self._repo.usable_link(raw_token, self._clock.now())
        if link is None:
            raise NotFound("This questionnaire link is invalid, already used or has expired.")
        return link

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
        verifier_ids = [i.verified_by_id for i in ctx.access if i.verified_by_id]
        verifiers = await self._repo.users(verifier_ids)
        answers = ctx.state.questionnaire_answers or {}
        state = ctx.state
        return OnboardingDetail(
            client_id=ctx.client.id,
            client_name=ctx.client.name,
            client_code=ctx.client.code,
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
            contract=state.contract,  # type: ignore[arg-type]  # DB check constraint
            contract_signed_at=state.contract_signed_at,
            questionnaire=state.questionnaire,  # type: ignore[arg-type]
            questionnaire_sent_at=state.questionnaire_sent_at,
            questionnaire_submitted_at=state.questionnaire_submitted_at,
            questions=[
                QuestionOut(key=key, label=label, answer=answers.get(key))
                for key, label in QUESTIONS
            ],
            access=[
                AccessItemOut(
                    key=i.key,
                    label=i.label,
                    status=i.status,  # type: ignore[arg-type]
                    verified_by=_ref(verifiers[i.verified_by_id])
                    if i.verified_by_id in verifiers
                    else None,
                    verified_at=i.verified_at,
                )
                for i in ctx.access
            ],
            kpis=[
                KpiOut(
                    id=k.id,
                    metric=k.metric,
                    baseline=k.baseline,
                    target=k.target,
                    unit=k.unit,
                    confirmed_by_name=k.confirmed_by_name,
                    confirmed_via=k.confirmed_via,
                    confirmed_at=k.confirmed_at,
                )
                for k in ctx.kpis
            ],
            kickoff_client=KickoffOut(
                status=state.kickoff_client,  # type: ignore[arg-type]
                at=state.kickoff_client_at,
                notes=state.kickoff_client_notes,
            ),
            kickoff_internal=KickoffOut(
                status=state.kickoff_internal,  # type: ignore[arg-type]
                at=state.kickoff_internal_at,
                notes=state.kickoff_internal_notes,
            ),
            team=[_ref(u) for u in ctx.team],
            reviewed_at=state.reviewed_at,
            completed_at=state.completed_at,
            permissions=Permissions(
                manage=self._can_manage(actor, ctx) and state.completed_at is None,
                verify_access=actor.can(ONBOARDING_ACCESS_VERIFY) and state.completed_at is None,
                confirm_kpis=actor.can(ONBOARDING_KPI_CONFIRM) and state.completed_at is None,
            ),
        )
