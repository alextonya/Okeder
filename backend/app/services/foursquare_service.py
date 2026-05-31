"""
Foursquare Places API v3 — recherche de venues.
Gratuit : 1000 requêtes/jour.
Inscription : https://foursquare.com/developer
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)

FSQ_BASE = "https://api.foursquare.com/v3"

# Mapping vibe/activité → catégories Foursquare
CATEGORY_MAP: dict[str, list[int]] = {
    # Activités
    "dinner":    [13065, 13032],   # Restaurant, Café
    "drinks":    [13003, 13002],   # Bar, Nightlife
    "brunch":    [13065, 13032],
    "cinema":    [10024],          # Movie Theater
    "concert":   [10032],          # Music Venue
    "activity":  [18000, 10000],   # Recreation, Arts
    # Vibes
    "casual":    [13065, 13003],
    "festive":   [13002, 10032],
    "cosy":      [13032, 13065],
    "outdoor":   [16000, 18000],   # Outdoors
    "cultural":  [10000],          # Arts & Entertainment
    "professional": [13065],
}


async def search_venues(
    query: str,
    near: str,
    radius_meters: int = 2000,
    vibe: str = "",
    activity: str = "",
    limit: int = 5,
    ll: str | None = None,   # "lat,lng" — prioritaire sur near si fourni
) -> list[dict]:
    """
    Recherche des venues via Foursquare Places API.
    Retourne une liste de dicts avec : name, address, rating, category, fsq_id, url.
    """
    if not settings.foursquare_api_key:
        logger.warning("FOURSQUARE_API_KEY non definie — recherche venue desactivee")
        return []


    # Construire les catégories à partir de la vibe et de l'activité
    cats: set[int] = set()
    for key in [activity, vibe]:
        if key and key in CATEGORY_MAP:
            cats.update(CATEGORY_MAP[key])
    if not cats:
        cats = {13065, 13003}  # Restaurant + Bar par défaut

    params: dict = {
        "query":      query or activity or vibe or "restaurant",
        "radius":     radius_meters,
        "limit":      limit,
        "categories": ",".join(str(c) for c in cats),
        "fields":     "name,location,rating,categories,fsq_id,website,price,photos",
        "sort":       "RATING",
    }
    # Priorité aux coordonnées exactes (midpoint), fallback sur texte
    if ll:
        params["ll"] = ll
    else:
        params["near"] = near

    logger.info(f"Foursquare search: query='{params['query']}' {'ll='+ll if ll else 'near='+near} radius={radius_meters}m")

    try:
        import asyncio
        import json as _json
        import urllib.parse
        import urllib.request

        query_string = urllib.parse.urlencode(params)
        url = f"{FSQ_BASE}/places/search?{query_string}"

        def _fetch():
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": settings.foursquare_api_key,
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                return _json.loads(r.read().decode())

        data = await asyncio.to_thread(_fetch)

        results = []
        for place in data.get("results", []):
            loc = place.get("location", {})
            cat_list = place.get("categories", [])
            cat_name = cat_list[0].get("name", "") if cat_list else ""

            # Prix Foursquare : 1=€, 2=€€, 3=€€€, 4=€€€€
            price_level = place.get("price", 0)
            price_str = "€" * price_level if price_level else "?"

            results.append({
                "name":    place.get("name", ""),
                "address": loc.get("formatted_address", ""),
                "city":    loc.get("locality", ""),
                "rating":  place.get("rating"),         # 0–10
                "category": cat_name,
                "price":   price_str,
                "fsq_id":  place.get("fsq_id", ""),
                "url":     place.get("website", ""),
                "photo":   _get_photo_url(place),
            })
        return results

    except Exception as e:
        logger.warning(f"Foursquare search failed ({type(e).__name__}): {e}")
        return []


def _get_photo_url(place: dict) -> str:
    try:
        photos = place.get("photos", [])
        if photos:
            p = photos[0]
            return f"{p['prefix']}300x200{p['suffix']}"
    except Exception:
        pass
    return ""


def pick_best_venue(venues: list[dict], budget_target_cents: int) -> dict | None:
    """Sélectionne le meilleur venue en fonction du budget et du rating."""
    if not venues:
        return None

    # Filtrer par budget si possible (heuristique : prix Foursquare)
    price_budget_map = {1: 2500, 2: 5000, 3: 8000, 4: 15000}  # cents par personne
    candidates = []
    for v in venues:
        price_level = len(v.get("price", ""))
        estimated_cost = price_budget_map.get(price_level, 5000)
        if budget_target_cents == 0 or estimated_cost <= budget_target_cents * 1.3:
            candidates.append(v)

    if not candidates:
        candidates = venues  # Fallback : tous

    # Trier par rating décroissant
    candidates.sort(key=lambda v: v.get("rating") or 0, reverse=True)
    return candidates[0]
