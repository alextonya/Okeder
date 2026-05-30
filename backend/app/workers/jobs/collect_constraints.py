"""
Job : collecte des contraintes.
Envoie un DM Telegram à chaque membre du groupe pour l'event donné.
"""
import uuid

from arq import ArqRedis

from app.config import settings
from app.database import AsyncSessionLocal


async def collect_constraints(ctx: dict, event_id: str) -> None:
    """Envoie un DM de collecte de contraintes à chaque membre du groupe."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select

        from app.models.event import Event
        from app.models.group import GroupMembership
        from app.models.member import Member

        result = await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))
        event = result.scalar_one_or_none()
        if not event:
            return

        members_result = await db.execute(
            select(Member).join(
                GroupMembership, Member.id == GroupMembership.member_id
            ).where(GroupMembership.group_id == event.group_id)
        )
        members = members_result.scalars().all()

        redis: ArqRedis = ctx["redis"]
        for member in members:
            if member.telegram_user_id:
                await redis.enqueue_job("send_constraint_dm", event_id, str(member.id))


async def send_constraint_dm(ctx: dict, event_id: str, member_id: str) -> None:
    """Envoie le DM de collecte à un membre spécifique via Telegram."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select

        from app.models.event import Event
        from app.models.member import Member
        from app.services.notification_service import send_telegram_message

        member_result = await db.execute(select(Member).where(Member.id == uuid.UUID(member_id)))
        member = member_result.scalar_one_or_none()
        if not member or not member.telegram_user_id:
            return

        event_result = await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))
        event = event_result.scalar_one_or_none()
        if not event:
            return

        text = (
            f"👋 Hey! A group outing is being planned.\n\n"
            f"<b>{event.title or 'Group event'}</b>\n\n"
            f"I need 3 quick answers to find the best option for everyone. "
            f"Your answers are private — no one else will see them.\n\n"
            f"Ready? /start_preferences_{event_id}"
        )
        await send_telegram_message(member.telegram_user_id, text)


async def check_and_trigger_engine(event_id: str, db) -> None:
    """Vérifie si le quorum est atteint et déclenche le moteur si c'est le cas."""
    from sqlalchemy.future import select

    from app.models.event import Event, EventStatus
    from app.models.group import GroupMembership
    from app.models.preference import Preference

    event_result = await db.execute(
        select(Event).where(Event.id == uuid.UUID(event_id))
    )
    event = event_result.scalar_one_or_none()
    if not event or event.wizard_mode:
        return  # En mode wizard, l'initiateur déclenche manuellement

    members_result = await db.execute(
        select(GroupMembership).where(GroupMembership.group_id == event.group_id)
    )
    total_members = len(members_result.scalars().all())

    prefs_result = await db.execute(
        select(Preference).where(
            Preference.event_id == uuid.UUID(event_id),
            Preference.submitted_at != None,  # noqa: E711
        )
    )
    submitted = len(prefs_result.scalars().all())

    # Quorum = 60% des membres ont répondu
    quorum_threshold = max(1, int(total_members * 0.6))
    if submitted >= quorum_threshold:
        from app.workers.jobs.run_decision_engine import enqueue_run_decision_engine
        await enqueue_run_decision_engine(event_id)


async def enqueue_collect_constraints(event_id: str) -> None:
    from app.workers.arq_settings import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("collect_constraints", event_id)
