"""
Job L6 : exécution du booking.
Chaîne de fallback : Eventbrite API → formulaire pré-rempli → agent IA (disclosé).
"""
import uuid
from datetime import datetime, timezone

from app.database import AsyncSessionLocal


async def execute_booking(ctx: dict, proposal_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select

        from app.models.booking_execution import BookingExecution, BookingMethod, BookingStatus
        from app.models.proposal import Proposal

        proposal_result = await db.execute(
            select(Proposal).where(Proposal.id == uuid.UUID(proposal_id))
        )
        proposal = proposal_result.scalar_one_or_none()
        if not proposal:
            return

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
        except Exception as e:
            execution.status = BookingStatus.FAILED
            execution.error_detail = str(e)
            # TODO M5 : chaîne de fallback prefilled_form → ai_browser_agent

        await db.commit()


async def _try_eventbrite(proposal) -> dict:
    from app.services.eventbrite_service import search_events, get_ticket_classes, create_order

    if not proposal.category:
        raise ValueError("No category on proposal")

    events = await search_events(
        query=proposal.category,
        location="London, UK",
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
