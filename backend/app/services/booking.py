"""
Okeder Concierge — réservation par CASCADE de canaux, pilotée par la réservabilité.

Idée : on connaît, pour chaque lieu, les canaux disponibles (balises OSM stockées
dans proposal.legitimacy_json["venue_contact"]). On route vers le canal le plus
AUTOMATISÉ possible et on dégrade proprement :

  Tier 1 — instantané : lien TheFork / Google Reserve pré-rempli (1 tap, dispo réelle)
  Tier 2 — assisté    : message rédigé (IA ou template) + envoi 1 tap WhatsApp/appel/email
  Tier 3 — agent IA   : formulaire rempli automatiquement (flag, disclosé) → cf. ai_booking_agent

Aucune clé requise pour Tier 1–2 : fonctionne partout. La confirmation est suivie
dans booking_executions (machine à états dans confirmation_data["state"]).
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus

from sqlalchemy.future import select

from app.models.booking_execution import BookingExecution, BookingMethod, BookingStatus
from app.models.proposal import Proposal


# ─── États de la réservation (stockés dans confirmation_data["state"]) ────────
class BookingState:
    READY = "ready"                          # assets générés, prêt à envoyer
    OUTREACH_SENT = "outreach_sent"          # un membre a déclenché l'envoi
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    FAILED = "failed"


def _venue_contact(proposal: Proposal) -> dict:
    lj = proposal.legitimacy_json or {}
    return lj.get("venue_contact") or {}


def _normalize_phone(phone: str) -> str:
    """Garde les chiffres (et un éventuel + initial) pour wa.me / tel:."""
    if not phone:
        return ""
    p = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")
    digits = re.sub(r"[^\d]", "", p)
    return digits


def _guess_lang(address: str) -> str:
    """Devine la langue du message au resto. FR par défaut (produit France-first)."""
    a = (address or "").lower()
    en_markers = ("united kingdom", "london", "uk", ", usa", "united states", "ireland", "dublin")
    if any(m in a for m in en_markers):
        return "en"
    return "fr"


def _open_url(proposal: Proposal) -> str:
    """Fiche du lieu (Google Reserve y apparaît si dispo)."""
    if proposal.external_url:
        return proposal.external_url
    q = " ".join(filter(None, [proposal.venue_name, proposal.venue_address])) or "restaurant"
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(q)}"


def _thefork_url(proposal: Proposal) -> str:
    contact = _venue_contact(proposal)
    if contact.get("book_url"):
        return contact["book_url"]
    q = proposal.venue_name or "restaurant"
    return f"https://www.thefork.com/search?cigleads={quote_plus(q)}&query={quote_plus(q)}"


def _template_message(proposal: Proposal, organiser_name: str, party_size: int, lang: str) -> str:
    when = ""
    venue = proposal.venue_name or ("votre établissement" if lang == "fr" else "your venue")
    name = organiser_name or "Okeder"
    if proposal.date_time:
        if lang == "fr":
            when = " le " + proposal.date_time.strftime("%d/%m à %H:%M")
        else:
            when = " on " + proposal.date_time.strftime("%d/%m at %H:%M")
    if lang == "fr":
        return (
            f"Bonjour, je souhaite réserver une table pour {party_size} personne(s) "
            f"au nom de {name}{when} chez {venue}. "
            "Pouvez-vous me confirmer la disponibilité ? Merci !"
        )
    return (
        f"Hello, I'd like to book a table for {party_size} "
        f"under the name {name}{when} at {venue}. "
        "Could you please confirm availability? Thank you!"
    )


async def draft_reservation_message(
    proposal: Proposal, organiser_name: str, party_size: int, lang: str | None = None
) -> str:
    """Message de réservation. IA (OpenAI) si clé dispo, sinon template localisé.
    Ne lève jamais : retombe sur le template à la moindre erreur."""
    from app.config import settings

    lang = lang or _guess_lang(proposal.venue_address or "")
    fallback = _template_message(proposal, organiser_name, party_size, lang)

    if not getattr(settings, "openai_api_key", ""):
        return fallback

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        when = proposal.date_time.strftime("%d/%m %H:%M") if proposal.date_time else "à convenir"
        prompt = (
            "Rédige un message court, poli et naturel pour réserver une table de restaurant. "
            f"Langue: {'français' if lang == 'fr' else 'anglais'}. "
            f"Restaurant: {proposal.venue_name or '-'}. Nombre de personnes: {party_size}. "
            f"Date/heure: {when}. Au nom de: {organiser_name or 'Okeder'}. "
            "Demande une confirmation de disponibilité. Réponds UNIQUEMENT par le message, sans guillemets."
        )
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=160,
            temperature=0.5,
        )
        msg = (resp.choices[0].message.content or "").strip()
        return msg or fallback
    except Exception:
        return fallback


def _detect_channel(contact: dict) -> tuple[str, int]:
    """Retourne (canal_recommandé, tier)."""
    if contact.get("book_url") or contact.get("reservation") in ("yes", "required"):
        return "thefork", 1
    if contact.get("whatsapp"):
        return "whatsapp", 2
    if contact.get("phone"):
        return "phone", 2
    if contact.get("email"):
        return "email", 2
    if contact.get("website"):
        return "website", 2
    return "manual", 2


async def build_cascade(proposal: Proposal, organiser_name: str, party_size: int) -> dict:
    """Construit la cascade complète d'actions de réservation pour ce lieu."""
    contact = _venue_contact(proposal)
    reservation = (proposal.legitimacy_json or {}).get("reservation") or {}
    lang = _guess_lang(proposal.venue_address or "")
    message = await draft_reservation_message(proposal, organiser_name, party_size, lang)

    # Le lien profond exact du Resolver prime sur tout (fiche resto prête à réserver).
    reserve_link = reservation.get("deep_link") or ""
    if reserve_link:
        recommended, tier = "reserve", 1
    else:
        recommended, tier = _detect_channel(contact)

    phone_digits = _normalize_phone(contact.get("whatsapp") or contact.get("phone") or "")
    wa_link = (
        f"https://wa.me/{phone_digits}?text={quote(message)}"
        if (contact.get("whatsapp") and phone_digits) else ""
    )
    tel_link = f"tel:{contact.get('phone')}" if contact.get("phone") else ""
    subject = (
        f"Réservation {proposal.venue_name or ''} — {party_size} pers."
        if lang == "fr" else
        f"Booking {proposal.venue_name or ''} — {party_size} people"
    )
    email_link = (
        f"mailto:{contact['email']}?subject={quote(subject)}&body={quote(message)}"
        if contact.get("email") else ""
    )

    return {
        "recommended": recommended,
        "tier": tier,
        "platform": reservation.get("platform", ""),
        "reservable": bool(reservation.get("reservable")),
        "channels": {
            "reserve":  reserve_link,
            "thefork":  _thefork_url(proposal),
            "open_url": _open_url(proposal),
            "call":     tel_link,
            "whatsapp": wa_link,
            "email":    email_link,
            "website":  contact.get("website", ""),
        },
        # clés rétro-compatibles (ancienne UI dashboard)
        "open_url":      _open_url(proposal),
        "thefork_url":   _thefork_url(proposal),
        "message":       message,
        "party_size":    party_size,
        "venue_name":    proposal.venue_name,
        "venue_address": proposal.venue_address,
        "datetime":      proposal.date_time.isoformat() if proposal.date_time else None,
        "contact":       contact,
        "state":         BookingState.READY,
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
    """Crée (ou met à jour) une exécution Concierge au statut 'in_progress'."""
    existing = await latest_booking(proposal.id, db)
    assets = await build_cascade(proposal, organiser_name, party_size)
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


async def mark_outreach_sent(proposal_id, channel: str, db) -> BookingExecution | None:
    """Un membre a déclenché l'envoi via un canal → on avance la machine à états."""
    be = await latest_booking(proposal_id, db)
    if not be:
        return None
    data = dict(be.confirmation_data or {})
    data["state"] = BookingState.AWAITING_CONFIRMATION
    data["sent_channel"] = channel
    be.confirmation_data = data
    be.attempted_at = datetime.now(timezone.utc)
    await db.commit()
    return be


async def confirm_booking(proposal_id, db) -> BookingExecution | None:
    """Marque la réservation confirmée (accord obtenu du lieu)."""
    be = await latest_booking(proposal_id, db)
    if not be:
        return None
    be.status = BookingStatus.SUCCESS
    be.completed_at = datetime.now(timezone.utc)
    data = dict(be.confirmation_data or {})
    data["state"] = BookingState.CONFIRMED
    be.confirmation_data = data
    await db.commit()
    return be


# ─── Rétro-compat : anciens helpers synchrones (encore importés ailleurs) ─────
def venue_open_url(proposal: Proposal) -> str:
    return _open_url(proposal)


def thefork_search_url(proposal: Proposal) -> str:
    return _thefork_url(proposal)


def reservation_message(proposal: Proposal, organiser_name: str, party_size: int) -> str:
    return _template_message(proposal, organiser_name, party_size, _guess_lang(proposal.venue_address or ""))
