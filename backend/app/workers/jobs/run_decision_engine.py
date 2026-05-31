"""
Job M3 : exécute le constraint engine (L3+L4) et crée la proposal en DB.
Si wizard_mode = False → publie automatiquement dans le groupe.
"""
import uuid

from app.database import AsyncSessionLocal


async def run_decision_engine(ctx: dict, event_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select

        from app.models.event import Event, EventStatus
        from app.models.preference import Preference
        from app.models.proposal import Proposal
        from app.services.constraint_engine import run_engine

        # ─── 1. Charger l'event et ses préférences ────────────────────────────
        event_result = await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))
        event = event_result.scalar_one_or_none()
        if not event:
            return

        prefs_result = await db.execute(
            select(Preference).where(
                Preference.event_id == uuid.UUID(event_id),
                Preference.submitted_at != None,  # noqa: E711
                Preference.declined == False,      # noqa: E712
            )
        )
        prefs = prefs_result.scalars().all()

        preferences = [
            {
                "budget_min":      p.budget_min,
                "budget_max":      p.budget_max,
                "category_prefs":  p.category_prefs or [],
                "hard_constraints": p.hard_constraints or [],
                "soft_preferences": p.soft_preferences or [],
                "available_slots": p.available_slots or [],
                "raw_answers":     p.raw_answers or {},
            }
            for p in prefs
        ]

        # ─── 2. Lancer le constraint engine ──────────────────────────────────
        spec = run_engine(preferences)

        # ─── 3. Rechercher un venue via Eventbrite ────────────────────────────
        # Priorité : event.location (saisi manuellement) > spec.location_hint (issu des prefs)
        location = event.location or spec.location_hint or "London"
        # Rayon : travel_time_max / 6 → ~5 km pour 30 min (vitesse piéton ~3 km/h + transports)
        radius_km = max(2, spec.travel_time_max // 6)

        venue_data = await _search_venue(
            category=spec.category or spec.vibe,
            location=location,
            radius_km=radius_km,
            budget_max_cents=spec.budget_target_cents,
        )

        # ─── 4. Créer la proposal en DB ───────────────────────────────────────
        version_result = await db.execute(
            select(Proposal).where(Proposal.event_id == uuid.UUID(event_id))
            .order_by(Proposal.version.desc()).limit(1)
        )
        last = version_result.scalar_one_or_none()
        next_version = (last.version + 1) if last else 1

        proposal = Proposal(
            event_id=uuid.UUID(event_id),
            version=next_version,
            title=venue_data.get("title") or spec.title,
            venue_name=venue_data.get("venue_name"),
            venue_address=venue_data.get("venue_address"),
            date_time=venue_data.get("date_time"),
            price_per_person=venue_data.get("price_cents") or spec.budget_target_cents,
            category=spec.category,
            external_url=venue_data.get("url"),
            pct_budget_satisfied=spec.pct_budget_satisfied,
            pct_time_satisfied=spec.pct_time_satisfied,
            pct_prefs_satisfied=spec.pct_prefs_satisfied,
            hard_constraints_met=spec.hard_constraints_met,
            compromise_flagged=spec.compromise_flagged,
            compromise_explanation=spec.compromise_explanation,
            legitimacy_json=spec.legitimacy_json,
            generated_by="engine",
            published=False,
        )
        db.add(proposal)

        # Mettre l'event en statut "proposed"
        event.status = EventStatus.PROPOSED
        await db.commit()
        await db.refresh(proposal)

        # ─── 5. Publier si pas en mode wizard ─────────────────────────────────
        if not event.wizard_mode:
            proposal.published = True
            await db.commit()
            from app.workers.jobs.send_proposal import enqueue_send_proposal
            await enqueue_send_proposal(str(proposal.id))


async def _search_venue(
    category: str,
    location: str,
    radius_km: int,
    budget_max_cents: int,
) -> dict:
    """
    Recherche un venue sur Eventbrite.
    Retourne un dict avec les infos du venue, ou un dict vide si rien trouvé.
    """
    try:
        from app.services.eventbrite_service import search_events

        events = await search_events(
            query=category,
            location=location,
            price_max_cents=budget_max_cents,
        )

        if not events:
            # Fallback : pas de venue spécifique, spec pure
            return {}

        best = events[0]
        venue = best.get("venue") or {}
        address = venue.get("address") or {}

        # Parser le prix
        price_cents = None
        try:
            price_val = best.get("ticket_availability", {}).get("minimum_ticket_price", {})
            if price_val:
                price_cents = int(float(price_val.get("major_value", 0)) * 100)
        except (ValueError, TypeError):
            pass

        # Parser la date
        date_time = None
        try:
            from datetime import datetime, timezone
            start_str = best.get("start", {}).get("utc", "")
            if start_str:
                date_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

        return {
            "title":         best.get("name", {}).get("text", ""),
            "venue_name":    venue.get("name", ""),
            "venue_address": address.get("localized_address_display", ""),
            "date_time":     date_time,
            "price_cents":   price_cents,
            "url":           best.get("url", ""),
        }

    except Exception as e:
        # Eventbrite indisponible → proposal sans venue spécifique
        import logging
        logging.getLogger(__name__).warning(f"Eventbrite search failed: {e}")
        return {}


async def enqueue_run_decision_engine(event_id: str) -> None:
    from app.workers.arq_settings import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("run_decision_engine", event_id)
