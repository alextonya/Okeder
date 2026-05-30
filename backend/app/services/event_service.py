import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.commitment import Commitment
from app.models.event import Event
from app.models.group import GroupMembership
from app.models.preference import Preference
from app.models.proposal import Proposal


async def get_full_summary(event_id: uuid.UUID, db: AsyncSession) -> dict:
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        return {}

    members_result = await db.execute(
        select(GroupMembership).where(GroupMembership.group_id == event.group_id)
    )
    member_count = len(members_result.scalars().all())

    prefs_result = await db.execute(
        select(Preference).where(Preference.event_id == event_id, Preference.declined == False)  # noqa: E712
    )
    prefs_count = len(prefs_result.scalars().all())

    proposal_result = await db.execute(
        select(Proposal)
        .where(Proposal.event_id == event_id, Proposal.published == True)  # noqa: E712
        .order_by(Proposal.version.desc())
        .limit(1)
    )
    proposal = proposal_result.scalar_one_or_none()

    commitments_count = {"soft": 0, "confirmed": 0, "hard": 0}
    if proposal:
        c_result = await db.execute(
            select(Commitment).where(Commitment.proposal_id == proposal.id)
        )
        for c in c_result.scalars().all():
            commitments_count[c.level] = commitments_count.get(c.level, 0) + 1

    return {
        "event_id": str(event_id),
        "status": event.status,
        "wizard_mode": event.wizard_mode,
        "member_count": member_count,
        "preferences_submitted": prefs_count,
        "proposal": {
            "id": str(proposal.id),
            "title": proposal.title,
            "published": proposal.published,
        } if proposal else None,
        "commitments": commitments_count,
    }


async def get_preference_status(event_id: uuid.UUID, db: AsyncSession) -> dict:
    members_result = await db.execute(
        select(GroupMembership).join(
            Event, GroupMembership.group_id == Event.group_id
        ).where(Event.id == event_id)
    )
    total = len(members_result.scalars().all())

    prefs_result = await db.execute(
        select(Preference).where(Preference.event_id == event_id, Preference.submitted_at != None)  # noqa: E711
    )
    submitted = len(prefs_result.scalars().all())

    return {"total_members": total, "submitted": submitted, "pending": total - submitted}
