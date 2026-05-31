"""
OpenStreetMap Overpass API — recherche de venues sans clé API.
Complètement gratuit. Fallback quand Foursquare n'est pas disponible.
"""
import asyncio
import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

# Mapping vibe/activité → types OSM
OSM_TAGS: dict[str, list[str]] = {
    "dinner":       ["amenity=restaurant", "amenity=bistro"],
    "drinks":       ["amenity=bar", "amenity=pub", "amenity=cocktail_bar"],
    "brunch":       ["amenity=cafe", "amenity=restaurant"],
    "lunch":        ["amenity=restaurant", "amenity=cafe"],
    "cinema":       ["amenity=cinema"],
    "concert":      ["amenity=music_venue", "amenity=nightclub"],
    "activity":     ["leisure=escape_game", "leisure=bowling_alley", "amenity=arts_centre"],
    # Vibes
    "casual":       ["amenity=pub", "amenity=bar", "amenity=restaurant"],
    "festive":      ["amenity=bar", "amenity=nightclub", "amenity=music_venue"],
    "cosy":         ["amenity=cafe", "amenity=wine_bar", "amenity=bistro"],
    "outdoor":      ["amenity=restaurant", "leisure=outdoor_seating"],
    "cultural":     ["amenity=arts_centre", "museum=yes", "amenity=theatre"],
    "professional": ["amenity=restaurant"],
}

DEFAULT_TAGS = ["amenity=restaurant", "amenity=bar", "amenity=cafe"]


async def search_venues(
    lat: float,
    lng: float,
    radius_meters: int = 2000,
    activity: str = "",
    vibe: str = "",
    limit: int = 5,
) -> list[dict]:
    """
    Recherche des venues via OpenStreetMap Overpass API.
    lat/lng = coordonnées du midpoint.
    """
    # Choisir les tags OSM
    tags = OSM_TAGS.get(activity, []) + OSM_TAGS.get(vibe, [])
    if not tags:
        tags = DEFAULT_TAGS
    # Dédupliquer
    tags = list(dict.fromkeys(tags))[:4]  # max 4 types

    # Construire la query Overpass
    tag_filters = "\n  ".join(
        f'node["{t.split("=")[0]}"="{t.split("=")[1]}"](around:{radius_meters},{lat},{lng});'
        for t in tags
    )
    query = f"""
[out:json][timeout:15];
(
  {tag_filters}
);
out {limit * 3} center;
"""

    def _fetch():
        encoded = urllib.parse.urlencode({"data": query}).encode()
        last_err = None
        for base_url in OVERPASS_URLS:
            try:
                req = urllib.request.Request(
                    base_url, data=encoded, method="POST",
                )
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                req.add_header("User-Agent", "Okeder/1.0 (okeder.app)")
                req.add_header("Accept", "application/json, */*")
                with urllib.request.urlopen(req, timeout=15) as r:
                    return json.loads(r.read().decode())
            except Exception as e:
                last_err = e
                continue
        raise last_err

    try:
        result = None
        for attempt in range(3):
            try:
                result = await asyncio.to_thread(_fetch)
                break
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(1)
                else:
                    raise

        venues = []
        seen_names = set()
        for el in result.get("elements", []):
            tags_data = el.get("tags", {})
            name = tags_data.get("name", "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            # Adresse
            addr_parts = []
            for key in ["addr:housenumber", "addr:street", "addr:city"]:
                v = tags_data.get(key, "")
                if v:
                    addr_parts.append(v)
            address = ", ".join(addr_parts) if addr_parts else ""

            # Cuisine / type
            cuisine = tags_data.get("cuisine", "")
            amenity = tags_data.get("amenity", "")
            category = cuisine or amenity or ""

            # Coordonnées
            v_lat = el.get("lat") or el.get("center", {}).get("lat")
            v_lng = el.get("lon") or el.get("center", {}).get("lon")

            venues.append({
                "name":    name,
                "address": address,
                "category": category.replace("_", " ").title(),
                "rating":   None,  # OSM n'a pas de rating
                "price":    tags_data.get("price", ""),
                "url":      tags_data.get("website", ""),
                "lat":      v_lat,
                "lng":      v_lng,
            })

            if len(venues) >= limit:
                break

        logger.info(f"Overpass: {len(venues)} venues found near {lat:.3f},{lng:.3f}")
        return venues

    except Exception as e:
        logger.warning(f"Overpass search failed: {e}")
        return []


def pick_best_venue(venues: list[dict]) -> dict | None:
    """Sélectionne le premier venue avec un nom."""
    if not venues:
        return None
    return venues[0]
