"""
Tests Okeder Concierge — réservabilité (OSM) + cascade de canaux.

Logique pure (pas de DB, pas de réseau : sans OPENAI_API_KEY, le message tombe
sur le template localisé).
"""
from types import SimpleNamespace

import pytest

from app.services import booking
from app.services.overpass_service import bookability_score, extract_contact


# ─── extract_contact ─────────────────────────────────────────────────────────

def test_extract_contact_reads_osm_tags():
    c = extract_contact({
        "phone": "+33 1 42 71 47 22",
        "contact:website": "https://le-resto.fr",
        "email": "hello@le-resto.fr",
        "reservation": "yes",
        "opening_hours": "Mo-Sa 12:00-23:00",
    })
    assert c["phone"] == "+33 1 42 71 47 22"
    assert c["website"] == "https://le-resto.fr"
    assert c["email"] == "hello@le-resto.fr"
    assert c["reservation"] == "yes"
    assert c["opening_hours"]


def test_extract_contact_detects_thefork_booking_url():
    c = extract_contact({"website": "https://www.thefork.com/restaurant/le-resto-12345"})
    assert c["book_url"]  # reconnu comme lien de réservation direct


def test_extract_contact_empty_when_no_tags():
    c = extract_contact({})
    assert c["phone"] == "" and c["book_url"] == ""


# ─── bookability_score : monotonie des canaux ────────────────────────────────

def test_bookability_ranks_channels():
    assert bookability_score({"book_url": "https://thefork.com/x"}) == 1.0
    assert bookability_score({"reservation": "yes"}) == 1.0
    assert bookability_score({"whatsapp": "+33..."}) == 0.85
    assert bookability_score({"phone": "+33..."}) == 0.7
    assert bookability_score({"email": "a@b.fr"}) == 0.5
    assert bookability_score({"website": "https://x.fr"}) == 0.4
    assert bookability_score({}) == 0.1


# ─── _detect_channel ─────────────────────────────────────────────────────────

def test_detect_channel_priority():
    assert booking._detect_channel({"book_url": "x"}) == ("thefork", 1)
    assert booking._detect_channel({"reservation": "required"}) == ("thefork", 1)
    assert booking._detect_channel({"whatsapp": "x"}) == ("whatsapp", 2)
    assert booking._detect_channel({"phone": "x"}) == ("phone", 2)
    assert booking._detect_channel({"email": "x"}) == ("email", 2)
    assert booking._detect_channel({}) == ("manual", 2)


# ─── build_cascade (async, template fallback sans clé OpenAI) ─────────────────

def _proposal(contact):
    return SimpleNamespace(
        legitimacy_json={"venue_contact": contact},
        venue_name="Le Petit Marché",
        venue_address="9 Rue de Béarn, Paris",
        date_time=None,
        external_url="https://maps.google.com/?q=Le+Petit+Marché",
    )


@pytest.mark.asyncio
async def test_build_cascade_phone_email_links():
    p = _proposal({"phone": "+33142714722", "email": "hi@resto.fr"})
    a = await booking.build_cascade(p, "Alex", 4)
    assert a["channels"]["call"] == "tel:+33142714722"
    assert a["channels"]["email"].startswith("mailto:hi@resto.fr")
    assert a["recommended"] == "phone"  # whatsapp absent → phone prioritaire
    assert a["message"]                  # message généré (template FR)
    assert "4" in a["message"]           # party size dans le message
    assert a["state"] == booking.BookingState.READY


@pytest.mark.asyncio
async def test_build_cascade_whatsapp_link_encoded():
    p = _proposal({"whatsapp": "+33 6 12 34 56 78"})
    a = await booking.build_cascade(p, "Sam", 2)
    assert a["channels"]["whatsapp"].startswith("https://wa.me/33612345678")
    assert a["recommended"] == "whatsapp"


@pytest.mark.asyncio
async def test_build_cascade_thefork_when_no_contact():
    p = _proposal({})
    a = await booking.build_cascade(p, "Lee", 3)
    assert a["channels"]["thefork"]            # toujours un lien TheFork de repli
    assert a["channels"]["open_url"]           # + fiche du lieu
    assert a["recommended"] == "manual"


@pytest.mark.asyncio
async def test_build_cascade_reserve_link_is_primary():
    p = _proposal({"phone": "+33142714722"})
    p.legitimacy_json["reservation"] = {
        "platform": "google_reserve", "deep_link": "https://maps.google.com/?q=place&query_place_id=abc",
        "reservable": True,
    }
    a = await booking.build_cascade(p, "Alex", 4)
    assert a["recommended"] == "reserve"       # le lien profond prime
    assert a["tier"] == 1
    assert a["channels"]["reserve"].endswith("query_place_id=abc")


# ─── Reservation Resolver (dégradable sans clé Google) ───────────────────────

@pytest.mark.asyncio
async def test_resolver_uses_osm_booking_website():
    from app.services.reservation_resolver import resolve
    r = await resolve(
        "Le Resto", "Paris", 48.85, 2.35,
        {"book_url": "https://www.thefork.com/restaurant/le-resto-r12345"},
    )
    assert r["platform"] == "thefork"
    assert r["reservable"] is True
    assert r["resolved_via"] == "osm_website"


@pytest.mark.asyncio
async def test_resolver_falls_back_without_google_key():
    # Pas de GOOGLE_MAPS_API_KEY en test → google_places renvoie None → repli propre
    from app.services.reservation_resolver import resolve
    r = await resolve("Le Resto", "Paris", 48.85, 2.35, {})
    assert r["platform"] == "none"
    assert r["deep_link"] == ""
    assert r["resolved_via"] == "fallback"
