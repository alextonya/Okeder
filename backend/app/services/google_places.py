"""
Wrapper Google **Places API (New)** — https://places.googleapis.com/v1

Une seule requête `places:searchText` suffit : avec un FieldMask riche elle renvoie
id (place_id), nom, adresse, site web, `reservable`, et l'URI Google Maps. Sert au
Reservation Resolver. Dégrade proprement : sans clé `GOOGLE_MAPS_API_KEY` → None.

⚠️ Nécessite l'API "Places API (New)" activée sur le projet Google Cloud
(console → APIs & Services → Enable APIs → "Places API (New)").
"""
import asyncio
import json
import logging
import urllib.request

from app.config import settings

log = logging.getLogger(__name__)
_SEARCH = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.websiteUri,places.reservable,places.googleMapsUri,"
    "places.nationalPhoneNumber"
)


def _key() -> str:
    return getattr(settings, "google_maps_api_key", "") or ""


async def find_place(name: str, address: str = "", lat: float | None = None, lng: float | None = None) -> dict | None:
    """Retrouve le lieu et renvoie un dict normalisé, ou None.

    {place_id, name, address, website, reservable, maps_uri, phone}
    """
    if not _key() or not name:
        return None

    body: dict = {"textQuery": ", ".join([p for p in (name, address) if p]), "maxResultCount": 1}
    if lat and lng:
        body["locationBias"] = {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 3000.0}}

    def _fetch():
        req = urllib.request.Request(
            _SEARCH,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": _key(),
                "X-Goog-FieldMask": _FIELD_MASK,
                "User-Agent": "Okeder/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())

    try:
        data = await asyncio.to_thread(_fetch)
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            detail = str(e)
        log.warning("Google Places (New) HTTP %s: %s", e.code, detail)
        return None
    except Exception as e:
        log.warning("Google Places (New) request failed: %s", e)
        return None

    places = (data or {}).get("places") or []
    if not places:
        return None
    p = places[0]
    return {
        "place_id":   p.get("id"),
        "name":       (p.get("displayName") or {}).get("text", ""),
        "address":    p.get("formattedAddress", ""),
        "website":    p.get("websiteUri", ""),
        "reservable": bool(p.get("reservable")),
        "maps_uri":   p.get("googleMapsUri", ""),
        "phone":      p.get("nationalPhoneNumber", ""),
    }
