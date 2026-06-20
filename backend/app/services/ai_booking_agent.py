"""
Tier 3 — Agent navigateur (réservation auto par remplissage de formulaire).

Appelle le service `booking-agent` (Playwright) qui remplit le widget de réservation
du resto. Principes non négociables :
  • TOUJOURS divulgué (le service signe nom + message "via Okeder").
  • JAMAIS l'unique voie : OFF par défaut (flag ENABLE_AI_BOOKING_AGENT).
  • Dégrade proprement : flag off / service injoignable / paiement-captcha-login / échec
    → fallback assisté (cascade). Ne lève jamais.
"""
import logging

log = logging.getLogger(__name__)


async def attempt_booking(proposal, assets: dict, organiser: dict | None = None) -> dict:
    """Tente la réservation auto via le service navigateur. Ne lève jamais.

    organiser: {name, email, phone} pour pré-remplir le formulaire.
    """
    from app.config import settings

    if not settings.enable_ai_booking_agent:
        return {"attempted": False, "reason": "disabled", "fallback": "assisted"}

    # Cible = widget web réservable. On préfère le site du resto / plateforme à la
    # fiche Maps (que l'agent ne peut pas piloter de façon fiable).
    reservation = (proposal.legitimacy_json or {}).get("reservation") or {}
    contact = (assets or {}).get("contact") or {}
    target = (
        reservation.get("website")
        or contact.get("book_url")
        or contact.get("website")
        or ""
    )
    if not target:
        return {"attempted": False, "reason": "no_web_widget", "fallback": "assisted", "disclosed": True}

    organiser = organiser or {}
    prefill = (assets or {}).get("prefill") or reservation.get("prefill") or {}
    date_iso = prefill.get("date_iso")
    hour = prefill.get("hour")
    payload = {
        "url": target,
        "party": int((assets or {}).get("party_size") or prefill.get("party") or 2),
        "date": date_iso,
        "time": (f"{int(hour):02d}:00" if hour not in (None, "") else None),
        "name": organiser.get("name", ""),
        "email": organiser.get("email", ""),
        "phone": organiser.get("phone", ""),
        "message": (assets or {}).get("message", ""),
        "auto_submit": True,  # policy: auto-submit sauf paiement (géré côté service)
    }

    try:
        import httpx

        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(settings.booking_agent_url.rstrip("/") + "/book", json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        log.warning("booking-agent unreachable/failed: %s", e)
        return {"attempted": False, "reason": "agent_unreachable", "fallback": "assisted", "disclosed": True}

    success = bool(data.get("success"))
    return {
        "attempted": True,
        "success": success,
        "disclosed": True,
        "stopped_reason": data.get("stopped_reason"),
        "confirmation": data.get("confirmation", ""),
        "screenshot_b64": data.get("screenshot_b64", ""),
        "steps": data.get("steps", []),
        "fallback": None if success else "assisted",
    }
