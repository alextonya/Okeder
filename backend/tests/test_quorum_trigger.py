"""
Tests de la logique de quorum (workers/jobs/collect_constraints.py).

C'est le déclencheur du moteur de décision (L3) : dès que 60% des participants
ont répondu, une 1ère proposal est générée ; puis re-déclenchement à 70/80/90/100%,
sans jamais déclencher deux fois le même seuil.

Un bug ici = des groupes qui ne reçoivent jamais de proposition, ou qui en
reçoivent en double. Logique non couverte jusqu'ici.

Sautés si aucune base Postgres de test n'est joignable.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.asyncio


async def _seed(sm, *, submitted: int, total_members: int = 5,
                expected_participants: int = 5, wizard_mode: bool = False,
                status: str = "collecting", n_proposals: int = 0) -> str:
    """Crée un event + N membres + `submitted` préférences soumises. Retourne event_id."""
    from app.models.event import Event
    from app.models.group import Group
    from app.models.member import Member
    from app.models.preference import Preference
    from app.models.proposal import Proposal

    async with sm() as s:
        g = Group(name="Quorum G")
        s.add(g)
        await s.flush()
        e = Event(
            group_id=g.id, title="Quorum E", status=status,
            wizard_mode=wizard_mode, expected_participants=expected_participants,
        )
        s.add(e)
        await s.flush()

        members = [Member(display_name=f"M{i}") for i in range(total_members)]
        for m in members:
            s.add(m)
        await s.flush()

        for i in range(submitted):
            s.add(Preference(
                event_id=e.id, member_id=members[i].id,
                submitted_at=datetime.now(timezone.utc), declined=False,
            ))
        for v in range(n_proposals):
            s.add(Proposal(event_id=e.id, version=v + 1, title="P", published=True))

        await s.commit()
        return str(e.id)


@pytest.fixture
def fake_engine(monkeypatch):
    """Remplace l'enqueue du moteur de décision par un mock (pas de Redis)."""
    mock = AsyncMock()
    monkeypatch.setattr(
        "app.workers.jobs.run_decision_engine.enqueue_run_decision_engine", mock
    )
    return mock


async def test_triggers_at_60_percent(sessionmaker_test, fake_engine):
    from app.workers.jobs.collect_constraints import _check_and_trigger_engine_inner

    event_id = await _seed(sessionmaker_test, submitted=3)  # 3/5 = 60%
    async with sessionmaker_test() as db:
        await _check_and_trigger_engine_inner(event_id, db)

    fake_engine.assert_awaited_once()
    assert fake_engine.await_args.args[0] == event_id


async def test_no_trigger_below_60_percent(sessionmaker_test, fake_engine):
    from app.workers.jobs.collect_constraints import _check_and_trigger_engine_inner

    event_id = await _seed(sessionmaker_test, submitted=2)  # 2/5 = 40%
    async with sessionmaker_test() as db:
        await _check_and_trigger_engine_inner(event_id, db)

    fake_engine.assert_not_awaited()


async def test_dedup_same_threshold_not_triggered_twice(sessionmaker_test, fake_engine):
    from app.workers.jobs.collect_constraints import _check_and_trigger_engine_inner

    # 60% atteint MAIS une proposal existe déjà (seuil 0 déjà traité) → pas de re-trigger
    event_id = await _seed(sessionmaker_test, submitted=3, n_proposals=1)
    async with sessionmaker_test() as db:
        await _check_and_trigger_engine_inner(event_id, db)

    fake_engine.assert_not_awaited()


async def test_higher_threshold_triggers_again(sessionmaker_test, fake_engine):
    from app.workers.jobs.collect_constraints import _check_and_trigger_engine_inner

    # 100% atteint (5/5), une seule proposal existante (60% traité) → nouveau seuil → trigger
    event_id = await _seed(sessionmaker_test, submitted=5, n_proposals=1)
    async with sessionmaker_test() as db:
        await _check_and_trigger_engine_inner(event_id, db)

    fake_engine.assert_awaited_once()


async def test_wizard_mode_never_triggers(sessionmaker_test, fake_engine):
    from app.workers.jobs.collect_constraints import _check_and_trigger_engine_inner

    event_id = await _seed(sessionmaker_test, submitted=5, wizard_mode=True)
    async with sessionmaker_test() as db:
        await _check_and_trigger_engine_inner(event_id, db)

    fake_engine.assert_not_awaited()


async def test_public_wrapper_swallows_errors(sessionmaker_test, fake_engine):
    """check_and_trigger_engine ne doit jamais propager d'exception (event_id invalide)."""
    from app.workers.jobs.collect_constraints import check_and_trigger_engine

    async with sessionmaker_test() as db:
        # event_id non-UUID → ValueError en interne, mais avalée par le wrapper
        await check_and_trigger_engine("not-a-uuid", db)

    fake_engine.assert_not_awaited()
