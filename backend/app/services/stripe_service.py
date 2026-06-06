import asyncio
import uuid

import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.commitment import Commitment, CommitmentLevel
from app.models.member import Member
from app.models.proposal import Proposal

stripe.api_key = settings.stripe_secret_key


def _ensure_key() -> None:
    """Réaffecte la clé au cas où l'env a été chargé après l'import."""
    stripe.api_key = settings.stripe_secret_key


def stripe_enabled() -> bool:
    return bool(settings.stripe_secret_key)


def deposit_amount_cents(proposal: Proposal) -> int:
    """Montant du dépôt = part par personne si connue, sinon défaut configuré."""
    return proposal.price_per_person or settings.deposit_default_cents


async def create_deposit_checkout(
    proposal: Proposal,
    member: Member,
    db: AsyncSession,
    success_url: str,
    cancel_url: str,
) -> str:
    """
    Crée une session Stripe Checkout (mode test) pour le dépôt 'Lock In'.
    Connect-ready : on pourra ajouter payment_intent_data.transfer_data.destination
    (compte Express du lieu/organisateur) + application_fee_amount pour ne jamais
    détenir les fonds. Pour le prototype : charge simple sur le compte plateforme test.
    """
    _ensure_key()
    amount = deposit_amount_cents(proposal)
    meta = {
        "okeder_proposal_id": str(proposal.id),
        "okeder_member_id": str(member.id),
        "okeder_event_id": str(proposal.event_id),
    }

    def _create():
        return stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": f"Deposit — {proposal.venue_name or 'Okeder outing'}"},
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            metadata=meta,
            payment_intent_data={"metadata": meta},
            success_url=success_url,
            cancel_url=cancel_url,
        )

    session = await asyncio.to_thread(_create)

    # Pré-enregistrer le montant + verrouiller le commitment au niveau Hard
    result = await db.execute(
        select(Commitment).where(
            Commitment.proposal_id == proposal.id,
            Commitment.member_id == member.id,
        )
    )
    commitment = result.scalar_one_or_none()
    if commitment:
        commitment.level = CommitmentLevel.HARD
        commitment.amount_cents = amount
    else:
        db.add(Commitment(
            proposal_id=proposal.id, member_id=member.id,
            level=CommitmentLevel.HARD, amount_cents=amount,
        ))
    await db.commit()
    return session.url


async def confirm_checkout_session(session_id: str, db: AsyncSession) -> dict:
    """Au retour de Checkout : vérifie le paiement et marque le commitment payé."""
    from datetime import datetime, timezone
    _ensure_key()

    def _retrieve():
        return stripe.checkout.Session.retrieve(session_id)

    try:
        session = await asyncio.to_thread(_retrieve)
    except Exception as e:
        return {"paid": False, "error": str(e)}

    if session.get("payment_status") != "paid":
        return {"paid": False, "status": session.get("payment_status")}

    md = session.get("metadata") or {}
    proposal_id = md.get("okeder_proposal_id")
    member_id = md.get("okeder_member_id")
    event_id = md.get("okeder_event_id")
    if not (proposal_id and member_id):
        return {"paid": True, "event_id": event_id}

    result = await db.execute(
        select(Commitment).where(
            Commitment.proposal_id == uuid.UUID(proposal_id),
            Commitment.member_id == uuid.UUID(member_id),
        )
    )
    commitment = result.scalar_one_or_none()
    if commitment and not commitment.paid_at:
        commitment.level = CommitmentLevel.HARD
        commitment.paid_at = datetime.now(timezone.utc)
        commitment.stripe_payment_intent_id = session.get("payment_intent")
        await db.commit()
        try:
            from app.workers.jobs.execute_booking import enqueue_execute_booking
            await enqueue_execute_booking(proposal_id)
        except Exception:
            pass
        try:
            from app.services.synthesis import update_initiator_synthesis
            if event_id:
                await update_initiator_synthesis(event_id, db)
        except Exception:
            pass

    return {"paid": True, "event_id": event_id, "member_id": member_id}


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
