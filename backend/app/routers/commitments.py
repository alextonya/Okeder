import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.deps import get_current_member
from app.models.commitment import Commitment, CommitmentLevel
from app.models.member import Member

router = APIRouter()


@router.post("/proposals/{proposal_id}/commitments", status_code=status.HTTP_201_CREATED)
async def upsert_commitment(
    proposal_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    level = body.get("level", CommitmentLevel.SOFT)
    result = await db.execute(
        select(Commitment).where(
            Commitment.proposal_id == proposal_id, Commitment.member_id == current_member.id
        )
    )
    commitment = result.scalar_one_or_none()
    if commitment:
        commitment.level = level
    else:
        commitment = Commitment(
            proposal_id=proposal_id, member_id=current_member.id, level=level
        )
        db.add(commitment)
    await db.commit()

    # Broadcast via WebSocket
    from app.routers.ws import broadcast_commitment_update
    await broadcast_commitment_update(str(proposal_id))

    return {"ok": True, "level": level}


@router.get("/proposals/{proposal_id}/commitments/me")
async def get_my_commitment(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    result = await db.execute(
        select(Commitment).where(
            Commitment.proposal_id == proposal_id, Commitment.member_id == current_member.id
        )
    )
    commitment = result.scalar_one_or_none()
    if not commitment:
        return {"level": None}
    return {"level": commitment.level, "paid": commitment.paid_at is not None}


@router.post("/proposals/{proposal_id}/commitments/me/pay")
async def initiate_payment(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Créer un Stripe PaymentIntent pour le niveau Hard."""
    from app.services.stripe_service import create_payment_intent
    client_secret = await create_payment_intent(proposal_id, current_member, db)
    return {"client_secret": client_secret}
