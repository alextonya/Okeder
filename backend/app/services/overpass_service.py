"""
OpenStreetMap Overpass API — recherche de venues sans clé API.
Scoring multicritères pour sélectionner le meilleur lieu.

Score(venue) =
  0.35 x distance_score   (minimise distance moyenne membres -> venue)
  0.22 x type_match       (vibe/activite correspond a la categorie OSM ?)
  0.13 x completeness     (adresse complete, nom propre, coordonnees)
  0.12 x fairness_score   (minimise l'inegalite entre membres)
  0.18 x bookability      (lieu facile a reserver : thefork/tel/whatsapp/email)
  x hard_constraint_penalty (0 si hard constraint viole -> elimine)
"""
import asyncio
import json
import logging
import math
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

OSM_TAGS: dict = {
    "dinner":       ["amenity=restaurant", "amenity=bistro"],
    "drinks":       ["amenity=bar", "amenity=pub", "amenity=cocktail_bar"],
    "brunch":       ["amenity=cafe", "amenity=restaurant"],
    "lunch":        ["amenity=restaurant", "amenity=cafe"],
    "cinema":       ["amenity=cinema"],
    "concert":      ["amenity=music_venue", "amenity=nightclub"],
    "activity":     ["leisure=escape_game", "leisure=bowling_alley", "amenity=arts_centre"],
    "casual":       ["amenity=pub", "amenity=bar", "amenity=restaurant"],
    "festive":      ["amenity=bar", "amenity=nightclub", "amenity=music_venue"],
    "cosy":         ["amenity=cafe", "amenity=wine_bar", "amenity=bistro"],
    "outdoor":      ["amenity=restaurant", "leisure=park"],
    "cultural":     ["amenity=arts_centre", "amenity=theatre"],
    "professional": ["amenity=restaurant"],
}
DEFAULT_TAGS = ["amenity=restaurant", "amenity=bar", "amenity=cafe"]

TYPE_KEYWORDS: dict = {
    "dinner":       ["restaurant", "bistro", "brasserie", "italian", "french", "asian", "indian"],
    "drinks":       ["bar", "pub", "cocktail", "wine", "taproom", "brewery"],
    "brunch":       ["cafe", "coffee", "bakery"],
    "lunch":        ["restaurant", "cafe", "deli"],
    "cinema":       ["cinema", "film", "movie"],
    "concert":      ["music", "live", "venue", "nightclub", "jazz"],
    "activity":     ["escape", "bowling", "climbing", "arcade", "game"],
    "casual":       ["pub", "bar", "restaurant", "bistro"],
    "festive":      ["bar", "cocktail", "nightclub", "lounge"],
    "cosy":         ["cafe", "wine", "bistro", "tearoom"],
    "professional": ["restaurant", "brasserie"],
}

HC_ELIMINATES: dict = {
    "no alcohol":   ["bar", "pub", "cocktail", "wine", "nightclub", "brewery"],
    "no_alcohol":   ["bar", "pub", "cocktail", "wine", "nightclub", "brewery"],
    "alcohol":      ["bar", "pub", "cocktail", "wine", "nightclub"],
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def extract_contact(tags: dict) -> dict:
    """Extrait les infos de réservabilité depuis les balises OSM d'un lieu.

    OSM expose souvent phone / website / email / contact:whatsapp / reservation /
    opening_hours. C'est ce qui permet à Okeder de savoir COMMENT réserver chaque
    lieu (cf. Okeder Concierge — la réservabilité pilote la sélection + la cascade).
    """
    def first(*keys):
        for k in keys:
            v = tags.get(k)
            if v and str(v).strip():
                return str(v).strip()
        return ""

    website = first("website", "contact:website", "url")
    wl = website.lower()
    book_url = website if any(p in wl for p in ("thefork", "lafourchette", "opentable", "resy", "bookatable")) else ""
    return {
        "phone":         first("phone", "contact:phone", "contact:mobile"),
        "whatsapp":      first("contact:whatsapp", "whatsapp"),
        "email":         first("email", "contact:email"),
        "website":       website,
        "book_url":      book_url,
        "reservation":   (tags.get("reservation") or "").lower(),  # yes / no / required
        "opening_hours": tags.get("opening_hours", ""),
    }


def bookability_score(contact: dict) -> float:
    """0→1 : à quel point ce lieu est facile à réserver (canal le plus fort dispo)."""
    if not contact:
        return 0.1
    if contact.get("book_url") or contact.get("reservation") in ("yes", "required"):
        return 1.0
    if contact.get("whatsapp"):
        return 0.85
    if contact.get("phone"):
        return 0.7
    if contact.get("email"):
        return 0.5
    if contact.get("website"):
        return 0.4
    return 0.1


def _score_venue(
    venue: dict,
    member_coords: list,
    activity: str,
    vibe: str,
    hard_constraints: list,
    radius_km: float,
) -> float:
    v_lat = venue.get("lat")
    v_lng = venue.get("lng")
    category = (venue.get("category") or "").lower()
    name = (venue.get("name") or "").lower()

    # Hard constraints — eliminatoires
    for constraint in hard_constraints:
        c = constraint.lower().strip()
        blacklist = HC_ELIMINATES.get(c, [])
        if blacklist and any(kw in category or kw in name for kw in blacklist):
            return 0.0

    # Distance score
    dist_score = 0.5
    fairness_score = 0.5
    if v_lat and v_lng and member_coords:
        dists = [_haversine(m[0], m[1], v_lat, v_lng) for m in member_coords]
        avg_d = sum(dists) / len(dists)
        norm = max(radius_km, 1.0)
        dist_score = max(0.0, 1.0 - avg_d / norm)

        if len(dists) > 1:
            variance = sum((d - avg_d) ** 2 for d in dists) / len(dists)
            std_dev = math.sqrt(variance)
            fairness_score = max(0.0, 1.0 - std_dev / norm)
        else:
            fairness_score = 1.0

    # Type match
    keywords = TYPE_KEYWORDS.get(activity, []) + TYPE_KEYWORDS.get(vibe, [])
    type_score = 1.0 if (keywords and any(kw in category or kw in name for kw in keywords)) else 0.2

    # Completeness
    completeness = 0.0
    if venue.get("name"):
        completeness += 0.5
    if venue.get("address"):
        completeness += 0.3
    if v_lat and v_lng:
        completeness += 0.2

    # Bookability — à qualité égale, on préfère un lieu facile à réserver.
    # C'est le pivot du Concierge : choisir le lieu en pensant déjà à la résa.
    book_score = bookability_score(venue.get("contact") or {})

    return round(
        0.35 * dist_score
        + 0.22 * type_score
        + 0.13 * completeness
        + 0.12 * fairness_score
        + 0.18 * book_score,
        4,
    )


def pick_best_venue(
    venues: list,
    member_coords: list | None = None,
    activity: str = "",
    vibe: str = "",
    hard_constraints: list | None = None,
    radius_km: float = 2.0,
) -> dict | None:
    if not venues:
        return None

    scored = [(
        _score_venue(v, member_coords or [], activity, vibe, hard_constraints or [], radius_km),
        v
    ) for v in venues]

    valid = [(s, v) for s, v in scored if s > 0]
    if not valid:
        logger.warning("All venues eliminated — using first")
        return venues[0]

    valid.sort(key=lambda x: x[0], reverse=True)
    best_score, best = valid[0]
    logger.info("Best venue: %s score=%.3f (%s)", best.get("name"), best_score, best.get("category"))

    # Log top 3 pour debug
    for s, v in valid[:3]:
        logger.debug("  %.3f — %s (%s)", s, v.get("name"), v.get("category"))

    return best


async def search_venues(
    lat: float,
    lng: float,
    radius_meters: int = 2000,
    activity: str = "",
    vibe: str = "",
    limit: int = 20,
) -> list:
    tags = OSM_TAGS.get(activity, []) + OSM_TAGS.get(vibe, [])
    if not tags:
        tags = DEFAULT_TAGS
    tags = list(dict.fromkeys(tags))[:5]

    tag_filters = "\n  ".join(
        'node["' + t.split("=")[0] + '"="' + t.split("=")[1] + '"](around:' + str(radius_meters) + ',' + str(lat) + ',' + str(lng) + ');'
        for t in tags
    )
    query = "[out:json][timeout:20];\n(\n  " + tag_filters + "\n);\nout " + str(limit) + " center;\n"

    def _fetch():
        encoded = urllib.parse.urlencode({"data": query}).encode()
        last_err = None
        for base_url in OVERPASS_URLS:
            try:
                req = urllib.request.Request(base_url, data=encoded, method="POST")
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                req.add_header("User-Agent", "Okeder/1.0 (okeder.app)")
                req.add_header("Accept", "application/json, */*")
                with urllib.request.urlopen(req, timeout=20) as r:
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
                    await asyncio.sleep(1.0)
                else:
                    raise

        venues = []
        seen: set = set()
        for el in result.get("elements", []):
            tags_data = el.get("tags", {})
            name = tags_data.get("name", "").strip()
            if not name or name in seen:
                continue
            seen.add(name)

            addr_parts = [tags_data.get(k, "") for k in ["addr:housenumber", "addr:street", "addr:city"] if tags_data.get(k)]
            address = ", ".join(addr_parts)

            cuisine = tags_data.get("cuisine", "")
            amenity = tags_data.get("amenity", tags_data.get("leisure", ""))
            category = (cuisine or amenity or "").replace("_", " ").title()

            v_lat = el.get("lat") or el.get("center", {}).get("lat")
            v_lng = el.get("lon") or el.get("center", {}).get("lon")

            venues.append({
                "name":     name,
                "address":  address,
                "category": category,
                "url":      tags_data.get("website", ""),
                "lat":      float(v_lat) if v_lat else None,
                "lng":      float(v_lng) if v_lng else None,
                "contact":  extract_contact(tags_data),
                "_tags":    tags_data,
            })

        logger.info("Overpass: %d raw venues near %.3f,%.3f", len(venues), lat, lng)
        return venues

    except Exception as e:
        logger.warning("Overpass search failed (%s): %s", type(e).__name__, e)
        return []
