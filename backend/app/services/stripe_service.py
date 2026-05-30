import uuid

import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.commitment import Commitment
from app.models.member import Member
from app.models.proposal import Proposal

stripe.api_key = settings.stripe_secret_key


async def create_payment_intent(
    proposal_id: uuid.UUID, member: Member, db: AsyncSession
) -> str:
    """Crée un Stripe PaymentIntent pour le niveau Hard Commit."""
    result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    proposal = result.scalar_one_or_none()
    if not proposal or not proposal.price_per_person:
        raise ValueError("Proposal not found or missing price")

    intent = stripe.PaymentIntent.create(
        amount=proposal.price_per_person,
        currency="eur",
        metadata={
            "okeder_proposal_id": str(proposal_id),
            "okeder_member_id": str(member.id),
        },
        automatic_payment_methods={"enabled": True},
    )

    # Pré-associer le payment intent au commitment
    result2 = await db.execute(
        select(Commitment).where(
            Commitment.proposal_id == proposal_id,
            Commitment.member_id == member.id,
        )
    )
    commitment = result2.scalar_one_or_none()
    if commitment:
        commitment.stripe_payment_intent_id = intent.id
        commitment.amount_cents = proposal.price_per_person
        await db.commit()

    return intent.client_secret


async def handle_stripe_event(event: dict, db: AsyncSession) -> None:
    """Traite les événements Stripe webhook."""
    event_type = event.get("type")

    if event_type == "payment_intent.succeeded":
        pi = event["data"]["object"]
        await _on_payment_succeeded(pi, db)
    elif event_type == "payment_intent.payment_failed":
        pi = event["data"]["object"]
        await _on_payment_failed(pi, db)


async def _on_payment_succeeded(pi: dict, db: AsyncSession) -> None:
    from datetime import datetime, timezone

    result = await db.execute(
        select(Commitment).where(Commitment.stripe_payment_intent_id == pi["id"])
    )
    commitment = result.scalar_one_or_none()
    if commitment:
        commitment.paid_at = datetime.now(timezone.utc)
        await db.commit()

        # Déclencher l'exécution du booking
        from app.workers.jobs.execute_booking import enqueue_execute_booking
        await enqueue_execute_booking(str(commitment.proposal_id))


async def _on_payment_failed(pi: dict, db: AsyncSession) -> None:
    # Saga : notifier le membre, laisser 24h pour réessayer
    pass  # TODO M4
