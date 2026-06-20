"""
Tests d'intégration des routers HTTP (FastAPI + base Postgres de test).

Couvre le parcours réel via l'API :
  L1 création d'event, L4 proposal/transparence, L5 commitment (upsert),
  L7 rating (validation), et le gating d'authentification.

Auth contournée via dependency_overrides (cf. conftest.py `client`).
Sautés automatiquement si aucune base Postgres de test n'est joignable.
"""
import uuid
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.asyncio


# ─── L1 — Groupe + Event ─────────────────────────────────────────────────────

async def test_create_group_returns_id(client):
    r = await client.post("/v1/groups", json={"name": "Les Potes"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Les Potes"
    uuid.UUID(body["id"])  # id est un UUID valide


async def test_create_event_starts_collecting_and_enqueues(client, monkeypatch):
    # Patch l'enqueue arq (pas de Redis nécessaire)
    fake_enqueue = AsyncMock()
    monkeypatch.setattr(
        "app.workers.jobs.collect_constraints.enqueue_collect_constraints", fake_enqueue
    )

    g = await client.post("/v1/groups", json={"name": "Dîner"})
    group_id = g.json()["id"]

    r = await client.post("/v1/events", json={"group_id": group_id, "title": "Resto"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "collecting"
    # L'event a bien déclenché la collecte de contraintes (L2)
    fake_enqueue.assert_awaited_once()
    assert fake_enqueue.await_args.args[0] == body["id"]


# ─── L7 — Rating : validation 1–5 ────────────────────────────────────────────

async def _make_event(client, monkeypatch):
    """Crée un groupe + un event via l'API et renvoie l'event_id."""
    monkeypatch.setattr(
        "app.workers.jobs.collect_constraints.enqueue_collect_constraints", AsyncMock()
    )
    g = await client.post("/v1/groups", json={"name": "Notes"})
    r = await client.post("/v1/events", json={"group_id": g.json()["id"], "title": "Resto"})
    return r.json()["id"]


async def test_rating_rejects_out_of_range(client):
    eid = str(uuid.uuid4())
    assert (await client.post(f"/v1/events/{eid}/ratings", json={"score": 0})).status_code == 422
    assert (await client.post(f"/v1/events/{eid}/ratings", json={"score": 6})).status_code == 422


async def test_rating_unknown_event_404(client):
    eid = str(uuid.uuid4())
    assert (await client.post(f"/v1/events/{eid}/ratings", json={"score": 4})).status_code == 404


async def test_rating_persists_and_upserts(client, monkeypatch, sessionmaker_test):
    eid = await _make_event(client, monkeypatch)

    r = await client.post(f"/v1/events/{eid}/ratings", json={"score": 4})
    assert r.status_code == 201
    assert r.json()["score"] == 4

    # Re-note → met à jour (contrainte unique event+member), pas de doublon
    r2 = await client.post(f"/v1/events/{eid}/ratings", json={"score": 2})
    assert r2.status_code == 201

    from sqlalchemy import select as sa_select
    from app.models.rating import Rating
    async with sessionmaker_test() as s:
        rows = (await s.execute(sa_select(Rating).where(Rating.event_id == uuid.UUID(eid)))).scalars().all()
    assert len(rows) == 1
    assert rows[0].score == 2


# ─── L5 — Commitment : upsert soft → confirmed ───────────────────────────────

async def _make_proposal(sm) -> str:
    """Crée group + event + proposal publiée en base, retourne proposal_id."""
    from app.models.event import Event
    from app.models.group import Group
    from app.models.proposal import Proposal

    async with sm() as s:
        g = Group(name="G")
        s.add(g)
        await s.flush()
        e = Event(group_id=g.id, title="E", status="proposed")
        s.add(e)
        await s.flush()
        p = Proposal(event_id=e.id, version=1, title="Chez Test", published=True)
        s.add(p)
        await s.commit()
        return str(p.id)


async def test_commitment_upsert_updates_level(client, sessionmaker_test):
    proposal_id = await _make_proposal(sessionmaker_test)

    r1 = await client.post(f"/v1/proposals/{proposal_id}/commitments", json={"level": "soft"})
    assert r1.status_code == 201
    assert r1.json()["level"] == "soft"

    me = await client.get(f"/v1/proposals/{proposal_id}/commitments/me")
    assert me.json()["level"] == "soft"

    # Re-commit → doit METTRE À JOUR (contrainte unique proposal+member), pas dupliquer
    r2 = await client.post(f"/v1/proposals/{proposal_id}/commitments", json={"level": "confirmed"})
    assert r2.status_code == 201
    me2 = await client.get(f"/v1/proposals/{proposal_id}/commitments/me")
    assert me2.json()["level"] == "confirmed"


async def test_commitment_level_validated(client, sessionmaker_test):
    """Le routeur rejette désormais un `level` hors enum (soft/confirmed/hard)."""
    proposal_id = await _make_proposal(sessionmaker_test)
    r = await client.post(f"/v1/proposals/{proposal_id}/commitments", json={"level": "banana"})
    assert r.status_code == 422


# ─── L4 — Proposal courante + bloc de transparence ───────────────────────────

async def test_current_proposal_404_when_none_published(client, sessionmaker_test):
    from app.models.event import Event
    from app.models.group import Group

    async with sessionmaker_test() as s:
        g = Group(name="G2")
        s.add(g)
        await s.flush()
        e = Event(group_id=g.id, title="E2")
        s.add(e)
        await s.commit()
        event_id = str(e.id)

    r = await client.get(f"/v1/events/{event_id}/proposals/current")
    assert r.status_code == 404


async def test_current_proposal_exposes_legitimacy_block(client, sessionmaker_test):
    from app.models.event import Event
    from app.models.group import Group
    from app.models.proposal import Proposal

    async with sessionmaker_test() as s:
        g = Group(name="G3")
        s.add(g)
        await s.flush()
        e = Event(group_id=g.id, title="E3")
        s.add(e)
        await s.flush()
        p = Proposal(
            event_id=e.id, version=1, title="Le Bistrot", published=True,
            pct_budget_satisfied=100, pct_time_satisfied=80, pct_prefs_satisfied=66,
            compromise_flagged=True, compromise_explanation="Venue 1.4km away",
            legitimacy_json={"vibe": "casual", "activity": "dinner"},
        )
        s.add(p)
        await s.commit()
        event_id = str(e.id)

    r = await client.get(f"/v1/events/{event_id}/proposals/current")
    assert r.status_code == 200
    body = r.json()
    # Le bloc de légitimité (L4) doit être exposé tel quel
    assert body["pct_budget_satisfied"] == 100.0
    assert body["pct_prefs_satisfied"] == 66.0
    assert body["compromise_flagged"] is True
    assert body["compromise_explanation"] == "Venue 1.4km away"
    assert body["legitimacy_json"]["vibe"] == "casual"


# ─── Auth — gating sans token ────────────────────────────────────────────────

async def test_endpoint_requires_auth(sessionmaker_test, seeded_member):
    """Sans override d'auth ni header Authorization → 401 (HTTPBearer).

    NB : les versions récentes de FastAPI renvoient 401 (sémantiquement correct
    pour une authentification absente) là où d'anciennes versions renvoyaient 403.
    On accepte les deux pour rester robuste au pinning de version."""
    from httpx import ASGITransport, AsyncClient

    from app.database import get_db
    from app.main import app

    async def _override_db():
        async with sessionmaker_test() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db  # DB ok, mais PAS d'auth
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/v1/groups", json={"name": "X"})
        assert r.status_code in (401, 403)
    finally:
        app.dependency_overrides.clear()
