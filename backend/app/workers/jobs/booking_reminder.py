"""
Cron Concierge — relance la réservation tant qu'elle n'est pas confirmée.

Balaye les propositions publiées dont l'event n'est pas encore réservé et envoie
UNE relance à l'organisateur (Telegram DM si possible, sinon push), avec le lien
/result. Idempotent : on marque `reminded` dans la booking_execution pour ne pas
spammer. Best-effort : n'interrompt jamais le worker.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

from app.database import AsyncSessionLocal

log = logging.getLogger(__name__)


async def booking_reminder(ctx: dict) -> int:
    """Retourne le nombre de relances envoyées (pour les logs/tests)."""
    sent = 0
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select

        from app.models.event import Event, EventStatus
        from app.models.member import Member
        from app.models.proposal import Proposal
        from app.services.booking import latest_booking, request_restaurant_booking, BookingState
        from app.models.booking_execution import BookingStatus

        now = datetime.now(timezone.utc)
        # Fenêtre : proposition publiée il y a >2h et <48h, event encore "proposed".
        lo = now - timedelta(hours=48)
        hi = now - timedelta(hours=2)

        rows = (await db.execute(
            select(Proposal, Event)
            .join(Event, Event.id == Proposal.event_id)
            .where(
                Proposal.published == True,            # noqa: E712
                Event.status == EventStatus.PROPOSED,
                Proposal.created_at < hi,
                Proposal.created_at > lo,
            )
        )).all()

        for proposal, event in rows:
            try:
                be = await latest_booking(proposal.id, db)
                if be and be.status == BookingStatus.SUCCESS:
                    continue
                data = (be.confirmation_data if be else None) or {}
                if data.get("reminded"):
                    continue
                if data.get("state") == BookingState.CONFIRMED:
                    continue

                # Organisateur
                creator = None
                if event.created_by:
                    creator = (await db.execute(
                        select(Member).where(Member.id == event.created_by)
                    )).scalar_one_or_none()

                public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")
                result_url = f"{public_url}/result/{event.id}"
                msg = (
                    "⏰ <b>Reminder</b>\nYour outing at "
                    + (proposal.venue_name or "the venue")
                    + " isn't booked yet. Lock the table in one tap:\n"
                    + result_url
                )

                notified = await _notify(creator, msg, result_url, proposal, db)
                if notified:
                    sent += 1

                # Marque 'reminded' (crée une exécution support si besoin)
                if be:
                    d = dict(data)
                    d["reminded"] = True
                    be.confirmation_data = d
                    await db.commit()
                else:
                    organiser = creator.display_name if creator and creator.display_name else "Okeder"
                    fresh = await request_restaurant_booking(proposal, organiser, 2, db)
                    d = dict(fresh.confirmation_data or {})
                    d["reminded"] = True
                    fresh.confirmation_data = d
                    await db.commit()
            except Exception as e:
                log.warning("booking_reminder failed for proposal %s: %s", proposal.id, e)

    if sent:
        log.info("booking_reminder: sent %d reminder(s)", sent)
    return sent


async def _notify(creator, msg: str, result_url: str, proposal, db) -> bool:
    """Telegram DM si possible, sinon push aux abonnements de l'organisateur."""
    from sqlalchemy.future import select
    from app.models.push_subscription import PushSubscription

    if creator and creator.telegram_user_id:
        try:
            from app.services.notification_service import send_telegram_message
            await send_telegram_message(creator.telegram_user_id, msg)
            return True
        except Exception:
            pass

    if creator:
        try:
            subs = (await db.execute(
                select(PushSubscription).where(PushSubscription.member_id == creator.id)
            )).scalars().all()
            if subs:
                from app.services.push_service import send_push_to_all
                await send_push_to_all(
                    subscriptions=[{"endpoint": s.endpoint, "keys": s.keys} for s in subs],
                    title="⏰ Lock the table",
                    body=(proposal.venue_name or "Your outing") + " isn't booked yet",
                    url=result_url,
                )
                return True
        except Exception:
            pass
    return False
