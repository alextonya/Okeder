"""
L6 — Eventbrite API : recherche et achat de tickets.
Méthode primaire conforme (API officielle, coût = 0 hors frais ticket).
"""
import httpx

from app.config import settings

EVENTBRITE_API = "https://www.eventbriteapi.com/v3"
HEADERS = {"Authorization": f"Bearer {settings.eventbrite_private_token}"}


async def search_events(
    query: str,
    location: str,
    date_range: dict | None = None,
    price_max_cents: int | None = None,
) -> list[dict]:
    params = {
        "q": query,
        "location.address": location,
        "expand": "venue,ticket_availability",
    }
    if date_range:
        params["start_date.range_start"] = date_range.get("start", "")
        params["start_date.range_end"] = date_range.get("end", "")

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{EVENTBRITE_API}/events/search/", headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()

    events = data.get("events", [])
    if price_max_cents:
        events = [
            e for e in events
            if _min_price_cents(e) <= price_max_cents
        ]
    return events


async def get_ticket_classes(event_id: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{EVENTBRITE_API}/events/{event_id}/ticket_classes/", headers=HEADERS
        )
        resp.raise_for_status()
        return resp.json().get("ticket_classes", [])


async def create_order(
    event_id: str, ticket_class_id: str, quantity: int, attendees: list[dict]
) -> dict:
    payload = {
        "order": {
            "event_id": event_id,
            "attendees": [
                {"ticket_class_id": ticket_class_id, "profile": a}
                for a in attendees
            ],
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{EVENTBRITE_API}/orders/", headers=HEADERS, json=payload
        )
        resp.raise_for_status()
        return resp.json()


async def handle_eventbrite_webhook(body: dict, db) -> None:
    pass  # TODO M5


def _min_price_cents(event: dict) -> int:
    try:
        return int(event["ticket_availability"]["minimum_ticket_price"]["major_value"]) * 100
    except (KeyError, TypeError, ValueError):
        return 0
