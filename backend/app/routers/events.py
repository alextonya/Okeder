import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.deps import get_current_member
from app.models.event import Event, EventStatus
from app.models.member import Member

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_event(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    deadline = datetime.now(timezone.utc) + timedelta(hours=48)
    event = Event(
        group_id=uuid.UUID(body["group_id"]),
        title=body.get("title"),
        wizard_mode=body.get("wizard_mode", True),
        constraint_deadline=deadline,
        created_by=current_member.id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # Enqueue constraint collection job
    from app.workers.jobs.collect_constraints import enqueue_collect_constraints
    await enqueue_collect_constraints(str(event.id))

    return {"id": str(event.id), "status": event.status}


@router.get("/{event_id}/summary")
async def get_event_summary(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    from app.services.event_service import get_full_summary
    return await get_full_summary(event_id, db)


@router.post("/{event_id}/ratings", status_code=status.HTTP_201_CREATED)
async def submit_rating(
    event_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Note post-event (1–5). Alimentera le profil comportemental à M6."""
    from app.models.rating import Rating

    score = int(body.get("score", 0))
    if not 1 <= score <= 5:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Score must be 1–5")

    # L'event doit exister (sinon 404 propre plutôt qu'une violation de FK)
    ev = await db.execute(select(Event).where(Event.id == event_id))
    if ev.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    # Upsert : une seule note par (event, member)
    result = await db.execute(
        select(Rating).where(
            Rating.event_id == event_id, Rating.member_id == current_member.id
        )
    )
    rating = result.scalar_one_or_none()
    if rating:
        rating.score = score
    else:
        db.add(Rating(event_id=event_id, member_id=current_member.id, score=score))
    await db.commit()
    # TODO M6 : update_behavioral_profile
    return {"ok": True, "score": score}
