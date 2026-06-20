"""
Job L6 — exécution de la réservation (Okeder Concierge), déclenché après acompte.

Cascade : Eventbrite API (événements ticketés) → agent IA navigateur (si flag)
→ cascade assistée (formulaire/lien/message pré-remplis). Ne dead-end jamais :
un acompte payé aboutit toujours à une réservation actionnable.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.database import AsyncSessionLocal

log = logging.getLogger(__name__)

# Catégories réellement ticketées → Eventbrite pertinent. Sinon (resto, bar…) on
# va directement à la cascade assistée.
TICKETED = {"concert", "cinema", "activity"}


async def execute_booking(ctx: dict, proposal_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select

        from app.models.booking_execution import BookingExecution, BookingMethod, BookingStatus
        from app.models.event import Event
        from app.models.member import Member
        from app.models.proposal import Proposal

        proposal = (await db.execute(
            select(Proposal).where(Proposal.id == uuid.UUID(proposal_id))
        )).scalar_one_or_none()
        if not proposal:
            return

        # 1. Eventbrite pour les catégories ticketées uniquement
        if (proposal.category or "") in TICKETED:
            execution = BookingExecution(
                proposal_id=proposal.id,
                method=BookingMethod.EVENTBRITE_API,
                status=BookingStatus.IN_PROGRESS,
                attempted_at=datetime.now(timezone.utc),
            )
            db.add(execution)
            await db.flush()
            try:
                result = await _try_eventbrite(proposal)
                execution.status = BookingStatus.SUCCESS
                execution.external_booking_id = result.get("id")
                execution.external_url = result.get("resource_uri")
                execution.confirmation_data = result
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return
            except Exception as e:
                execution.status = BookingStatus.FAILED
                execution.error_detail = str(e)
                await db.commit()
                log.info("Eventbrite booking failed (%s) — falling back to Concierge cascade", e)

        # 2. Contexte organisateur + taille du groupe (pour le message)
        organiser_name = "Okeder"
        organiser = {}
        if proposal.event_id:
            event = (await db.execute(
                select(Event).where(Event.id == proposal.event_id)
            )).scalar_one_or_none()
            if event and event.created_by:
                creator = (await db.execute(
                    select(Member).where(Member.id == event.created_by)
                )).scalar_one_or_none()
                if creator:
                    organiser_name = creator.display_name or organiser_name
                    organiser = {
                        "name": creator.display_name or "",
                        "email": creator.email or "",
                        "phone": creator.phone or "",
                    }
        party_size = await _party_size(proposal.id, db)

        # 3. Agent IA navigateur (flag, disclosé) — sinon fallback assisté
        from app.services.ai_booking_agent import attempt_booking
        from app.services.booking import build_cascade
        from app.services.booking import BookingState

        assets = await build_cascade(proposal, organiser_name, party_size)
        agent = await attempt_booking(proposal, assets, organiser)

        if agent.get("attempted") and agent.get("success"):
            be = BookingExecution(
                proposal_id=proposal.id,
                method=BookingMethod.AI_BROWSER_AGENT,
                status=BookingStatus.SUCCESS,
                external_url=agent.get("url") or assets["open_url"],
                confirmation_data={**assets, "state": BookingState.CONFIRMED, "agent": agent},
                agent_disclosed=True,
                attempted_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db.add(be)
            await db.commit()
            return

        # 4. Cascade assistée — toujours actionnable (Tier 1–2)
        be = BookingExecution(
            proposal_id=proposal.id,
            method=BookingMethod.PREFILLED_FORM,
            status=BookingStatus.IN_PROGRESS,
            external_url=assets["open_url"],
            confirmation_data={**assets, "agent": agent},
            agent_disclosed=bool(agent.get("disclosed")),
            attempted_at=datetime.now(timezone.utc),
        )
        db.add(be)
        await db.commit()


async def _party_size(proposal_id, db) -> int:
    from sqlalchemy.future import select
    from app.models.commitment import Commitment

    rows = (await db.execute(
        select(Commitment).where(Commitment.proposal_id == proposal_id)
    )).scalars().all()
    going = [c for c in rows if c.level in ("confirmed", "hard")]
    return max(1, len(going) or len(rows))


async def _try_eventbrite(proposal) -> dict:
    from app.services.eventbrite_service import search_events, get_ticket_classes, create_order

    if not proposal.category:
        raise ValueError("No category on proposal")

    events = await search_events(
        query=proposal.category,
        location=proposal.venue_address or "",
        price_max_cents=proposal.price_per_person,
    )
    if not events:
        raise ValueError("No Eventbrite events found matching criteria")

    best_event = events[0]
    ticket_classes = await get_ticket_classes(best_event["id"])
    if not ticket_classes:
        raise ValueError("No ticket classes available")

    return await create_order(
        event_id=best_event["id"],
        ticket_class_id=ticket_classes[0]["id"],
        quantity=1,
        attendees=[{"name": "Okeder Group"}],
    )


async def enqueue_execute_booking(proposal_id: str) -> None:
    from app.workers.arq_settings import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("execute_booking", proposal_id)
