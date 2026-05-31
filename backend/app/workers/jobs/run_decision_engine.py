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
            preferences=preferences,
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
        # Stocker coords pour les calculs de distance (pas pour Maps URL)
        spec.legitimacy_json["venue_lat"] = venue_data.get("lat") or venue_lat
        spec.legitimacy_json["venue_lng"] = venue_data.get("lng") or venue_lng
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

        # Google Maps URL — toujours par NOM+ADRESSE pour pointer sur le bon établissement
        import urllib.parse as _ulp
        gmaps_url = ""
        vname = venue_data.get("venue_name", "")
        vaddr = venue_data.get("venue_address", "")
        if vname and vaddr:
            q = _ulp.quote(vname + ", " + vaddr)
            gmaps_url = "https://www.google.com/maps/search/?api=1&query=" + q
        elif vname:
            gmaps_url = "https://www.google.com/maps/search/?api=1&query=" + _ulp.quote(vname)

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
    preferences: list | None = None,
) -> dict:
    """
    Recherche un venue : Foursquare en priorité, Eventbrite en fallback.
    Retourne un dict normalisé ou {} si aucun résultat.
    """
    import logging
    log = logging.getLogger(__name__)

    radius_m = max(500, radius_km * 1000)

    # ─── OpenStreetMap Overpass (gratuit, sans clé, fiable) ──────────────────
    # Foursquare supprimé — API renvoie 410 Gone
    # Si pas de coordonnées GPS → geocoder la zone texte
    if not (midpoint_lat and midpoint_lng) and location:
        midpoint_lat, midpoint_lng = await _geocode(location, log)
        if midpoint_lat:
            log.info("Geocoded '%s' -> %.4f,%.4f", location, midpoint_lat, midpoint_lng)
        else:
            log.warning("Geocoding failed for '%s' — no venue search possible", location)

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
            # Coordonnées membres : GPS si dispo, sinon géocoder le texte
            member_coords = []
            for p in preferences:
                raw = p.get("raw_answers") or {}
                m_lat = raw.get("departure_lat")
                m_lng = raw.get("departure_lng")
                if m_lat and m_lng:
                    try:
                        member_coords.append((float(m_lat), float(m_lng)))
                    except (ValueError, TypeError):
                        pass
                elif raw.get("departure_text"):
                    g_lat, g_lng = await _geocode(raw["departure_text"], log)
                    if g_lat and g_lng:
                        member_coords.append((g_lat, g_lng))
                        log.info("Geocoded member '%s' -> %.4f,%.4f", raw.get("departure_text"), g_lat, g_lng)
            # Collecter les hard constraints de tous les membres
            all_hard = []
            for p in preferences:
                all_hard.extend(p.get("hard_constraints") or [])

            venue = osm_pick(
                venues,
                member_coords=member_coords,
                activity=activity,
                vibe=vibe,
                hard_constraints=all_hard,
                radius_km=radius_m / 1000,
            )
            if venue:
                name    = venue.get("name", "").strip()
                address = venue.get("address", "").strip()
                v_lat   = venue.get("lat")
                v_lng   = venue.get("lng")

                log.info("Selected venue: '%s' | '%s' | lat=%s lng=%s", name, address, v_lat, v_lng)

                if not name:
                    log.warning("Venue has no name — skipping")
                else:
                    category = venue.get("category", "")
                    title = name + (" — " + category if category else "")
                    return {
                        "title":         title,
                        "venue_name":    name,
                        "venue_address": address,
                        "date_time":     None,
                        "price_cents":   None,
                        "lat":           v_lat,
                        "lng":           v_lng,
                    }
            else:
                log.warning("Overpass returned %d venues but scoring eliminated all", len(venues))
        except Exception as e:
            log.warning("Overpass search failed: %s", e)

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


async def _geocode(location: str, log) -> tuple[float | None, float | None]:
    """
    Convertit un texte de zone en coordonnées GPS.
    1. Photon (komoot) — HTTP, pas de TLS
    2. Villes connues — fallback hardcodé
    """
    import json as _j
    import urllib.parse as _up
    import urllib.request as _ur

    # Villes connues — évite le geocodage pour les cas communs
    KNOWN = {
        "london": (51.5074, -0.1278), "paris": (48.8566, 2.3522),
        "new york": (40.7128, -74.0060), "manchester": (53.4808, -2.2426),
        "birmingham": (52.4862, -1.8904), "leeds": (53.8008, -1.5491),
        "edinburgh": (55.9533, -3.1883), "glasgow": (55.8642, -4.2518),
        "bristol": (51.4545, -2.5879), "liverpool": (53.4084, -2.9916),
        "lyon": (45.7640, 4.8357), "marseille": (43.2965, 5.3698),
        "bordeaux": (44.8378, -0.5792), "toulouse": (43.6047, 1.4442),
        "amsterdam": (52.3676, 4.9041), "berlin": (52.5200, 13.4050),
        "madrid": (40.4168, -3.7038), "barcelona": (41.3851, 2.1734),
    }
    loc_lower = location.lower().strip()
    for key, coords in KNOWN.items():
        if key in loc_lower:
            return coords

    # Photon (komoot) — utilise HTTP interne, plus robuste sur Python 3.14
    try:
        q = _up.urlencode({"q": location, "limit": "1"})
        url = "https://photon.komoot.io/api/?" + q
        req = _ur.Request(url, headers={"User-Agent": "Okeder/1.0"})
        with _ur.urlopen(req, timeout=8) as r:
            data = _j.loads(r.read().decode())
        features = data.get("features", [])
        if features:
            coords = features[0]["geometry"]["coordinates"]
            return float(coords[1]), float(coords[0])  # [lng, lat] → (lat, lng)
    except Exception as e:
        log.warning("Photon geocoding failed: %s", e)

    # Nominatim fallback
    try:
        q = _up.urlencode({"q": location, "format": "json", "limit": "1"})
        req = _ur.Request(
            "https://nominatim.openstreetmap.org/search?" + q,
            headers={"User-Agent": "Okeder/1.0"},
        )
        with _ur.urlopen(req, timeout=8) as r:
            results = _j.loads(r.read().decode())
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        log.warning("Nominatim geocoding failed: %s", e)

    return None, None


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
