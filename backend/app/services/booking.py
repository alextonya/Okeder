"""
L6b — Réservation restaurant via formulaire/lien pré-rempli (sans API partenaire).
Génère : un lien d'ouverture du lieu (Google Reserve/Maps), un message de réservation
prêt à envoyer, et trace l'exécution dans booking_executions.
Aucune clé requise — fonctionne partout (Europe d'abord).
"""
import uuid
from datetime import datetime, timezone
from urllib.parse import quote_plus

from sqlalchemy.future import select

from app.models.booking_execution import BookingExecution, BookingMethod, BookingStatus
from app.models.proposal import Proposal


def venue_open_url(proposal: Proposal) -> str:
    """Lien pour ouvrir la fiche du lieu (Google Reserve y apparaît si dispo)."""
    if proposal.external_url:
        return proposal.external_url
    q = " ".join(filter(None, [proposal.venue_name, proposal.venue_address])) or "restaurant"
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(q)}"


def thefork_search_url(proposal: Proposal) -> str:
    q = proposal.venue_name or "restaurant"
    return f"https://www.thefork.com/search?query={quote_plus(q)}"


def reservation_message(proposal: Proposal, organiser_name: str, party_size: int) -> str:
    when = ""
    if proposal.date_time:
        when = " le " + proposal.date_time.strftime("%d/%m à %H:%M")
    venue = proposal.venue_name or "votre établissement"
    name = organiser_name or "Okeder"
    return (
        f"Bonjour, je souhaite réserver une table pour {party_size} personne(s) "
        f"au nom de {name}{when} chez {venue}. Merci de me confirmer la disponibilité."
    )


def booking_assets(proposal: Proposal, organiser_name: str, party_size: int) -> dict:
    return {
        "open_url": venue_open_url(proposal),
        "thefork_url": thefork_search_url(proposal),
        "message": reservation_message(proposal, organiser_name, party_size),
        "party_size": party_size,
        "venue_name": proposal.venue_name,
        "venue_address": proposal.venue_address,
        "datetime": proposal.date_time.isoformat() if proposal.date_time else None,
    }


async def latest_booking(proposal_id, db) -> BookingExecution | None:
    res = await db.execute(
        select(BookingExecution)
        .where(BookingExecution.proposal_id == proposal_id)
        .order_by(BookingExecution.attempted_at.desc().nullslast())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def request_restaurant_booking(
    proposal: Proposal, organiser_name: str, party_size: int, db
) -> BookingExecution:
    """Crée (ou met à jour) une exécution L6b 'prefilled_form' au statut 'requested'."""
    existing = await latest_booking(proposal.id, db)
    assets = booking_assets(proposal, organiser_name, party_size)
    now = datetime.now(timezone.utc)
    if existing and existing.status in (BookingStatus.PENDING, BookingStatus.IN_PROGRESS):
        existing.confirmation_data = assets
        existing.external_url = assets["open_url"]
        existing.attempted_at = now
        be = existing
    else:
        be = BookingExecution(
            proposal_id=proposal.id,
            method=BookingMethod.PREFILLED_FORM,
            status=BookingStatus.IN_PROGRESS,
            external_url=assets["open_url"],
            confirmation_data=assets,
            attempted_at=now,
        )
        db.add(be)
    await db.commit()
    return be


async def confirm_booking(proposal_id, db) -> BookingExecution | None:
    """Marque la réservation comme confirmée (l'organisateur a eu l'accord du lieu)."""
    be = await latest_booking(proposal_id, db)
    if not be:
        return None
    be.status = BookingStatus.SUCCESS
    be.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return be
