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
    """Note post-event (1–5). Déclenche la mise à jour du profil comportemental à M6."""
    score = int(body.get("score", 0))
    if not 1 <= score <= 5:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Score must be 1–5")
    # TODO M6 : stocker en DB + update_behavioral_profile
    return {"ok": True, "score": score}
