import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.deps import get_current_member
from app.models.member import Member
from app.models.preference import Preference

router = APIRouter()


@router.post("/events/{event_id}/preferences", status_code=status.HTTP_201_CREATED)
async def submit_preferences(
    event_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    result = await db.execute(
        select(Preference).where(
            Preference.event_id == event_id, Preference.member_id == current_member.id
        )
    )
    pref = result.scalar_one_or_none()
    if pref:
        for key, val in body.items():
            setattr(pref, key, val)
        pref.submitted_at = datetime.now(timezone.utc)
    else:
        pref = Preference(
            event_id=event_id,
            member_id=current_member.id,
            submitted_at=datetime.now(timezone.utc),
            **{k: v for k, v in body.items() if k not in ("event_id", "member_id")},
        )
        db.add(pref)
    await db.commit()

    # Check if quorum reached → trigger decision engine
    from app.workers.jobs.collect_constraints import check_and_trigger_engine
    await check_and_trigger_engine(str(event_id), db)

    return {"ok": True}


@router.get("/events/{event_id}/preferences/status")
async def preferences_status(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    from app.services.event_service import get_preference_status
    return await get_preference_status(event_id, db)
