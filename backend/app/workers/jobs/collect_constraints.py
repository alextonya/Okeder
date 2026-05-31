"""
Job : collecte des contraintes.
Envoie un DM Telegram à chaque membre humain du groupe pour l'event donné.
"""
import uuid

from arq import ArqRedis

from app.config import settings
from app.database import AsyncSessionLocal


async def collect_constraints(ctx: dict, event_id: str) -> None:
    """Envoie un DM de collecte de contraintes à chaque membre humain du groupe."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select

        from app.models.event import Event
        from app.models.group import GroupMembership
        from app.models.member import Member

        result = await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))
        event = result.scalar_one_or_none()
        if not event:
            return

        # Exclure le bot du décompte et des DMs
        bot_id = _get_bot_id()

        members_result = await db.execute(
            select(Member).join(
                GroupMembership, Member.id == GroupMembership.member_id
            ).where(
                GroupMembership.group_id == event.group_id,
                Member.telegram_user_id != bot_id,
            )
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

        bot_username = settings.telegram_bot_username or "OkederBot"
        deep_link = f"https://t.me/{bot_username}?start=event_{event_id}"

        text = (
            f"👋 Hey! A group outing is being planned.\n\n"
            f"<b>{event.title or 'Group event'}</b>\n\n"
            f"I need a few quick answers to find the best option for everyone. "
            f"Your answers are private — no one else will see them.\n\n"
            f'<a href="{deep_link}">Tap here to answer →</a>'
        )
        await send_telegram_message(member.telegram_user_id, text)


async def check_and_trigger_engine(event_id: str, db) -> None:
    """
    Vérifie si un nouveau seuil de quorum est atteint et déclenche le moteur.

    Seuils : 60% → 1ère proposal, puis 70%, 80%, 90%, 100% → mise à jour.
    Ne déclenche jamais deux fois au même seuil.
    Le bot est exclu du décompte.
    """
    try:
        await _check_and_trigger_engine_inner(event_id, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"check_and_trigger_engine failed silently: {e}"
        )


async def _check_and_trigger_engine_inner(event_id: str, db) -> None:
    from sqlalchemy import func
    from sqlalchemy.future import select

    from app.models.event import Event, EventStatus
    from app.models.group import GroupMembership
    from app.models.member import Member
    from app.models.preference import Preference
    from app.models.proposal import Proposal

    # ─── 1. Charger l'event ───────────────────────────────────────────────────
    event_result = await db.execute(
        select(Event).where(Event.id == uuid.UUID(event_id))
    )
    event = event_result.scalar_one_or_none()
    if not event or event.wizard_mode:
        return

    # Statuts éligibles
    eligible_statuses = (
        EventStatus.COLLECTING,
        EventStatus.DECIDING,
        EventStatus.PROPOSED,
    )
    if event.status not in eligible_statuses:
        return

    # ─── 2. Compter les membres humains ───────────────────────────────────────
    bot_id = _get_bot_id()
    members_result = await db.execute(
        select(Member)
        .join(GroupMembership, Member.id == GroupMembership.member_id)
        .where(
            GroupMembership.group_id == event.group_id,
            Member.telegram_user_id != bot_id,
        )
    )
    human_members = members_result.scalars().all()
    total = len(human_members)
    if total == 0:
        return

    # ─── 3. Compter les soumissions ───────────────────────────────────────────
    prefs_result = await db.execute(
        select(Preference).where(
            Preference.event_id == uuid.UUID(event_id),
            Preference.submitted_at != None,  # noqa: E711
            Preference.declined == False,      # noqa: E712
        )
    )
    submitted = len(prefs_result.scalars().all())

    # ─── 4. Calculer le seuil courant ─────────────────────────────────────────
    # Seuils : 60, 70, 80, 90, 100
    THRESHOLDS = [0.6, 0.7, 0.8, 0.9, 1.0]
    ratio = submitted / total

    # Trouver le plus haut seuil atteint
    current_level = None
    for t in THRESHOLDS:
        if ratio >= t:
            current_level = t

    if current_level is None:
        return  # Pas encore à 60%

    # ─── 5. Vérifier si ce seuil a déjà été traité ────────────────────────────
    # Nombre de proposals existantes = nombre de seuils déjà déclenchés
    prop_count_result = await db.execute(
        select(func.count(Proposal.id)).where(Proposal.event_id == uuid.UUID(event_id))
    )
    existing_proposals = prop_count_result.scalar() or 0

    # Index du seuil courant dans THRESHOLDS
    current_idx = THRESHOLDS.index(current_level)

    if existing_proposals > current_idx:
        return  # Ce seuil a déjà été traité

    # ─── 6. Déclencher l'engine ───────────────────────────────────────────────
    from app.workers.jobs.run_decision_engine import enqueue_run_decision_engine
    await enqueue_run_decision_engine(event_id)


def _get_bot_id() -> int | None:
    """Extrait le telegram_user_id du bot depuis le token."""
    token = settings.telegram_bot_token
    if token and ":" in token:
        try:
            return int(token.split(":")[0])
        except ValueError:
            pass
    return None


async def enqueue_collect_constraints(event_id: str) -> None:
    from app.workers.arq_settings import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("collect_constraints", event_id)
