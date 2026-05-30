import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.deps import get_current_member
from app.models.member import Member
from app.models.proposal import Proposal

router = APIRouter()


@router.get("/events/{event_id}/proposals/current")
async def get_current_proposal(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    result = await db.execute(
        select(Proposal)
        .where(Proposal.event_id == event_id, Proposal.published == True)  # noqa: E712
        .order_by(Proposal.version.desc())
        .limit(1)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No published proposal")
    return _serialize(proposal)


@router.post("/events/{event_id}/proposals", status_code=status.HTTP_201_CREATED)
async def create_proposal_wizard(
    event_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Wizard of Oz: initiateur crée manuellement une proposal."""
    result = await db.execute(
        select(Proposal).where(Proposal.event_id == event_id).order_by(Proposal.version.desc()).limit(1)
    )
    last = result.scalar_one_or_none()
    next_version = (last.version + 1) if last else 1

    proposal = Proposal(
        event_id=event_id,
        version=next_version,
        generated_by="wizard",
        **{k: v for k, v in body.items() if k not in ("event_id",)},
    )
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)
    return _serialize(proposal)


@router.post("/proposals/{proposal_id}/publish")
async def publish_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Wizard: publie la proposal dans le groupe Telegram."""
    result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    proposal.published = True
    await db.commit()

    from app.workers.jobs.send_proposal import enqueue_send_proposal
    await enqueue_send_proposal(str(proposal_id))
    return {"ok": True}


def _serialize(p: Proposal) -> dict:
    return {
        "id": str(p.id),
        "event_id": str(p.event_id),
        "version": p.version,
        "title": p.title,
        "venue_name": p.venue_name,
        "venue_address": p.venue_address,
        "date_time": p.date_time.isoformat() if p.date_time else None,
        "price_per_person": p.price_per_person,
        "category": p.category,
        "external_url": p.external_url,
        "pct_budget_satisfied": float(p.pct_budget_satisfied) if p.pct_budget_satisfied else None,
        "pct_time_satisfied": float(p.pct_time_satisfied) if p.pct_time_satisfied else None,
        "pct_prefs_satisfied": float(p.pct_prefs_satisfied) if p.pct_prefs_satisfied else None,
        "compromise_flagged": p.compromise_flagged,
        "compromise_explanation": p.compromise_explanation,
        "legitimacy_json": p.legitimacy_json,
        "generated_by": p.generated_by,
        "published": p.published,
    }
