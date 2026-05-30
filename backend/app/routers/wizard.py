"""
Wizard of Oz endpoints — réservés à l'initiateur authentifié.
Permettent de piloter manuellement le cycle de coordination pendant la phase M0–M2.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.deps import get_current_member
from app.models.event import Event, EventStatus
from app.models.member import Member

router = APIRouter()

VALID_TRANSITIONS = {
    EventStatus.COLLECTING: [EventStatus.DECIDING],
    EventStatus.DECIDING: [EventStatus.PROPOSED],
    EventStatus.PROPOSED: [EventStatus.COMMITTING],
    EventStatus.COMMITTING: [EventStatus.BOOKING],
    EventStatus.BOOKING: [EventStatus.CONFIRMED],
    EventStatus.CONFIRMED: [EventStatus.COMPLETED],
}


@router.get("/events")
async def list_wizard_events(
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    result = await db.execute(select(Event).where(Event.created_by == current_member.id))
    events = result.scalars().all()
    return [{"id": str(e.id), "title": e.title, "status": e.status} for e in events]


@router.post("/events/{event_id}/advance-status")
async def advance_status(
    event_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    target = body.get("status")
    allowed = VALID_TRANSITIONS.get(event.status, [])
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition {event.status} → {target}",
        )
    event.status = target
    await db.commit()
    return {"status": event.status}


@router.post("/events/{event_id}/trigger-engine")
async def trigger_engine(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Déclencher manuellement le constraint engine (L3)."""
    from app.workers.jobs.run_decision_engine import enqueue_run_decision_engine
    await enqueue_run_decision_engine(str(event_id))
    return {"ok": True, "message": "Engine job enqueued"}


@router.post("/events/{event_id}/send-proposal")
async def send_proposal(
    event_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Publier la proposal courante dans le groupe Telegram."""
    from sqlalchemy.future import select as sa_select

    from app.models.proposal import Proposal
    from app.workers.jobs.send_proposal import enqueue_send_proposal

    result = await db.execute(
        sa_select(Proposal)
        .where(Proposal.event_id == event_id)
        .order_by(Proposal.version.desc())
        .limit(1)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No proposal found")

    proposal.published = True
    await db.commit()
    await enqueue_send_proposal(str(proposal.id))
    return {"ok": True}
