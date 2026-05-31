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
            vibe=spec.vibe,
            activity=spec.category,
            location=location,
            radius_km=radius_km,
            budget_max_cents=spec.budget_target_cents,
            midpoint_lat=spec.midpoint_lat,
            midpoint_lng=spec.midpoint_lng,
        )

        # ─── 4. Calculer les distances membres → venue ────────────────────────
        venue_lat = venue_data.get("lat") or (spec.midpoint_lat if spec.midpoint_lat else None)
        venue_lng = venue_data.get("lng") or (spec.midpoint_lng if spec.midpoint_lng else None)

        distances_info = []
        if venue_lat and venue_lng:
            for p in preferences:
                raw = p.get("raw_answers") or {}
                m_lat = raw.get("departure_lat")
                m_lng = raw.get("departure_lng")
                m_name = raw.get("display_name", "Member")
                m_max = raw.get("travel_time_max", 30)
                if m_lat and m_lng:
                    dist_km = _haversine(float(m_lat), float(m_lng), venue_lat, venue_lng)
                    # Estimation temps : ~4 km/h à pied + transports
                    est_min = int(dist_km * 12)
                    over = est_min > (m_max if m_max != 999 else 999)
                    distances_info.append({
                        "name": m_name,
                        "dist_km": round(dist_km, 1),
                        "est_min": est_min,
                        "max_min": m_max,
                        "over_max": over,
                    })

        # Enrichir legitimacy_json avec distances et vibe
        spec.legitimacy_json["venue_lat"] = venue_lat
        spec.legitimacy_json["venue_lng"] = venue_lng
        spec.legitimacy_json["distances"] = distances_info
        spec.legitimacy_json["vibe_proposed"] = spec.vibe

        # ─── 5. Créer la proposal en DB ───────────────────────────────────────
        version_result = await db.execute(
            select(Proposal).where(Proposal.event_id == uuid.UUID(event_id))
            .order_by(Proposal.version.desc()).limit(1)
        )
        last = version_result.scalar_one_or_none()
        next_version = (last.version + 1) if last else 1

        # Construire le titre avec date hint
        title = venue_data.get("title") or spec.title
        if spec.datetime_hint and spec.datetime_hint != "TBD":
            title = f"{title} — {spec.datetime_hint}"

        # Google Maps URL avec coordonnées précises si disponibles
        gmaps_url = ""
        if venue_lat and venue_lng:
            gmaps_url = f"https://maps.google.com/?q={venue_lat},{venue_lng}&z=16"
        elif venue_data.get("venue_name") and venue_data.get("venue_address"):
            import urllib.parse
            q = urllib.parse.quote(f"{venue_data['venue_name']} {venue_data['venue_address']}")
            gmaps_url = f"https://maps.google.com/?q={q}"

        proposal = Proposal(
            event_id=uuid.UUID(event_id),
            version=next_version,
            title=title,
            venue_name=venue_data.get("venue_name"),
            venue_address=venue_data.get("venue_address"),
            date_time=venue_data.get("date_time"),
            price_per_person=venue_data.get("price_cents") or spec.budget_target_cents,
            category=spec.category,
            external_url=gmaps_url or venue_data.get("url"),
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
    vibe: str,
    activity: str,
    location: str,
    radius_km: int,
    budget_max_cents: int,
    midpoint_lat: float | None = None,
    midpoint_lng: float | None = None,
) -> dict:
    """
    Recherche un venue : Foursquare en priorité, Eventbrite en fallback.
    Retourne un dict normalisé ou {} si aucun résultat.
    """
    import logging
    log = logging.getLogger(__name__)

    radius_m = max(500, radius_km * 1000)

    # ─── 1. Foursquare (restaurants, bars, lieux) — si clé valide ────────────
    try:
        from app.services.foursquare_service import search_venues as fsq_search, pick_best_venue as fsq_pick
        from app.config import settings as _settings

        if _settings.foursquare_api_key and _settings.foursquare_api_key.startswith("fsq"):
            venues = await fsq_search(
                query=activity or vibe,
                near=location,
                radius_meters=radius_m,
                vibe=vibe,
                activity=activity,
                ll=f"{midpoint_lat},{midpoint_lng}" if midpoint_lat and midpoint_lng else None,
            )
            venue = fsq_pick(venues, budget_max_cents)
            if venue:
                title = venue["name"]
                if venue.get("category"):
                    title = f"{venue['name']} — {venue['category']}"
                return {
                    "title":         title,
                    "venue_name":    venue["name"],
                    "venue_address": venue.get("address", ""),
                    "date_time":     None,
                    "price_cents":   None,
                    "url":           venue.get("url", ""),
                }
        else:
            log.info("Foursquare key not valid (needs fsq3...) — using Overpass fallback")
    except Exception as e:
        log.warning(f"Foursquare search failed: {e}")

    # ─── 1b. OpenStreetMap Overpass (fallback gratuit, sans clé) ─────────────
    if midpoint_lat and midpoint_lng:
        try:
            from app.services.overpass_service import search_venues as osm_search, pick_best_venue as osm_pick

            venues = await osm_search(
                lat=midpoint_lat,
                lng=midpoint_lng,
                radius_meters=radius_m,
                activity=activity,
                vibe=vibe,
            )
            venue = osm_pick(venues)
            if venue:
                title = venue["name"]
                if venue.get("category"):
                    title = f"{venue['name']} — {venue['category']}"
                return {
                    "title":         title,
                    "venue_name":    venue["name"],
                    "venue_address": venue.get("address", ""),
                    "date_time":     None,
                    "price_cents":   None,
                    "url":           venue.get("url", ""),
                    "lat":           venue.get("lat"),
                    "lng":           venue.get("lng"),
                }
        except Exception as e:
            log.warning(f"Overpass search failed: {e}")

    # ─── 2. Eventbrite fallback (concerts, shows ticketés) ────────────────────
    try:
        from app.services.eventbrite_service import search_events

        events = await search_events(
            query=activity or vibe,
            location=location,
            price_max_cents=budget_max_cents,
        )
        if events:
            best = events[0]
            venue = best.get("venue") or {}
            address = venue.get("address") or {}
            price_cents = None
            try:
                pv = best.get("ticket_availability", {}).get("minimum_ticket_price", {})
                if pv:
                    price_cents = int(float(pv.get("major_value", 0)) * 100)
            except Exception:
                pass
            date_time = None
            try:
                from datetime import datetime
                s = best.get("start", {}).get("utc", "")
                if s:
                    date_time = datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
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
        log.warning(f"Eventbrite fallback failed: {e}")

    return {}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en km entre deux coordonnées GPS (formule Haversine)."""
    import math
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


async def enqueue_run_decision_engine(event_id: str) -> None:
    from app.workers.arq_settings import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("run_decision_engine", event_id)
