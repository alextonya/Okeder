"""Smoke-test end-to-end des nouvelles fonctionnalites (compte/OTP/decline/dashboard/quorum)."""
import asyncio
import hashlib
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

BASE = os.environ.get("TEST_BASE", "http://localhost:8000")
EMAIL = "tester@okeder.app"
CODE = "424242"
H = {"ngrok-skip-browser-warning": "1"}


def otp_hash(email, code):
    return hashlib.sha256(f"{email.lower()}:{code}:{settings.session_secret}".encode()).hexdigest()


async def seed_otp(engine):
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM otp_codes WHERE email=:e"), {"e": EMAIL})
        await conn.execute(text(
            "INSERT INTO otp_codes (id, email, code_hash, expires_at, consumed, attempts, created_at) "
            "VALUES (:id,:e,:h,:exp,false,0, now())"
        ), {"id": str(uuid.uuid4()), "e": EMAIL, "h": otp_hash(EMAIL, CODE),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10)})


async def main():
    url = os.environ["DATABASE_URL"]
    engine = create_async_engine(url, echo=False)
    await seed_otp(engine)

    async with httpx.AsyncClient(base_url=BASE, headers=H, timeout=30, follow_redirects=False) as c:
        # 1. Login via OTP
        r = await c.post("/pwa/auth/verify-otp", json={"email": EMAIL, "code": CODE, "name": "Alice Organiser"})
        print("1. verify-otp:", r.status_code, r.json())
        assert r.status_code == 200 and r.json()["ok"]
        mid = r.json()["member_id"]

        # 2. /pwa/auth/me authentifie
        r = await c.get("/pwa/auth/me")
        print("2. me:", r.json())
        assert r.json().get("authenticated")

        # 3. /create renvoie le formulaire (pas la page d'auth)
        r = await c.get("/create")
        is_form = "Plan a group outing" in r.text and "Send me a code" not in r.text
        print("3. /create shows form (authed):", is_form)
        assert is_form

        # 4. do-create -> redirect vers mini-app avec mid
        r = await c.get("/pwa/do-create", params={"title": "Test Dinner", "guests": 2})
        loc = r.headers.get("location", "")
        print("4. do-create redirect:", r.status_code, loc[:90])
        assert "mini-app" in loc and "mid=" in loc
        event_id = loc.split("/mini-app/")[1].split("?")[0]

        # 5. Organisateur soumet ses prefs (member_id = compte) -> pas de doublon
        r = await c.post("/mini-app/submit", json={
            "init_data": "", "member_id": mid, "event_id": event_id,
            "display_name": "Alice Organiser", "vibe": ["casual"], "activity": ["dinner"],
            "departure_text": "Paris", "travel_time_max": 30, "budget_min": 2000, "budget_max": 5000,
            "hard_constraints": [],
        })
        print("5. organiser submit:", r.status_code, r.json())
        assert r.json().get("member_id") == mid, "organiser must reuse account member (no duplicate)"

        # 6. Invite #1 soumet (nouveau membre web)
        r = await c.post("/mini-app/submit", json={
            "init_data": "", "member_id": None, "event_id": event_id,
            "display_name": "Bob Guest", "vibe": ["festive"], "activity": ["dinner"],
            "departure_text": "Paris", "travel_time_max": 45, "budget_min": 3000, "budget_max": 6000,
            "hard_constraints": [],
        })
        print("6. guest Bob submit:", r.status_code, r.json())

        # 7. Invite #2 DECLINE
        r = await c.post("/mini-app/decline", json={
            "init_data": "", "member_id": None, "event_id": event_id, "display_name": "Carol Guest",
        })
        print("7. guest Carol decline:", r.status_code, r.json())
        assert r.json().get("ok")

        # 8. Dashboard (compte initiateur)
        r = await c.get(f"/dashboard/{event_id}")
        ok_dash = r.status_code == 200 and "Organiser dashboard" in r.text
        print("8. dashboard:", r.status_code, "shows dashboard:", ok_dash,
              "| has Carol declined:", "Can&#39;t make it" in r.text or "Can't make it" in r.text)
        assert ok_dash

    # 9. Verifier en base : participants & doublon
    async with engine.begin() as conn:
        ev = uuid.UUID(event_id)
        prefs = (await conn.execute(text(
            "SELECT m.display_name, p.declined, p.submitted_at IS NOT NULL AS sub "
            "FROM preferences p JOIN members m ON m.id=p.member_id WHERE p.event_id=:e ORDER BY m.display_name"
        ), {"e": str(ev)})).fetchall()
        print("9. preferences in DB:")
        for row in prefs:
            print("   -", row[0], "| declined:", row[1], "| submitted:", row[2])
        # organisateur unique (pas de doublon Alice)
        alice = (await conn.execute(text(
            "SELECT count(*) FROM members WHERE display_name='Alice Organiser'"))).scalar()
        print("   Alice member rows (expect 1):", alice)
        assert alice == 1, "duplicate organiser member!"

    await engine.dispose()
    print("\nALL FEATURE CHECKS PASSED")


asyncio.run(main())
