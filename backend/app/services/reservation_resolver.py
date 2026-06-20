"""
Reservation Resolver — transforme un lieu OSM en IDENTITÉ de réservation + lien profond.

C'est la brique qui fait passer de "ouvrir une recherche" à "ouvrir LA fiche du
resto, prête à réserver". Exécuté à la publication de la proposition ; résultat mis
en cache dans proposal.legitimacy_json["reservation"].

Cascade de résolution :
  1. Site OSM déjà une plateforme de réservation (thefork/opentable/…) → on l'utilise.
  2. Google Places → place_id + reservable → deep link Maps "fiche exacte" (Reserve with Google).
  3. Repli → pas de lien exact (la cascade assistée prendra le relais).
"""
import logging
import urllib.parse

from app.services import google_places

log = logging.getLogger(__name__)

_PLATFORM_HOSTS = {
    "thefork": "thefork",
    "lafourchette": "thefork",
    "opentable": "opentable",
    "resy": "resy",
    "bookatable": "bookatable",
    "sevenrooms": "sevenrooms",
    "guestonline": "guestonline",
    "zenchef": "zenchef",
}


def _platform_of(url: str) -> str:
    u = (url or "").lower()
    for host, name in _PLATFORM_HOSTS.items():
        if host in u:
            return name
    return "website"


def _empty(prefill: dict) -> dict:
    return {
        "platform": "none",
        "deep_link": "",
        "reservable": False,
        "place_id": None,
        "website": "",
        "resolved_via": "fallback",
        "prefill": prefill,
    }


async def resolve(
    venue_name: str,
    venue_address: str,
    lat: float | None,
    lng: float | None,
    contact: dict | None,
    prefill: dict | None = None,
) -> dict:
    """Renvoie un dict reservation ; ne lève jamais."""
    contact = contact or {}
    prefill = prefill or {}

    # 1. Le site OSM est déjà une plateforme de réservation
    book_url = contact.get("book_url")
    if book_url:
        return {
            "platform": _platform_of(book_url),
            "deep_link": book_url,
            "reservable": True,
            "place_id": None,
            "website": book_url,
            "resolved_via": "osm_website",
            "prefill": prefill,
        }

    # 2. Google Places (New) → fiche exacte + reservable (1 requête)
    try:
        place = await google_places.find_place(venue_name, venue_address, lat, lng)
        if place and place.get("place_id"):
            pid = place["place_id"]
            q = urllib.parse.quote(venue_name or place.get("name", ""))
            deep = f"https://www.google.com/maps/search/?api=1&query={q}&query_place_id={pid}"
            website = place.get("website", "")
            # Si le site officiel est une plateforme de réservation connue → lien direct
            if website and _platform_of(website) != "website":
                return {
                    "platform": _platform_of(website),
                    "deep_link": website,
                    "reservable": True,
                    "place_id": pid,
                    "website": website,
                    "resolved_via": "google_places+website",
                    "prefill": prefill,
                }
            return {
                "platform": "google_reserve",
                "deep_link": deep,
                "reservable": bool(place.get("reservable")),
                "place_id": pid,
                "website": website,
                "resolved_via": "google_places",
                "prefill": prefill,
            }
    except Exception as e:
        log.warning("Reservation resolve failed: %s", e)

    # 3. Repli
    return _empty(prefill)
