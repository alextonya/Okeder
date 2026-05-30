"""Tests du constraint engine — pas de DB, testable sans infra."""
from app.services.constraint_engine import run_engine


def test_happy_path():
    prefs = [
        {"budget_min": 2000, "budget_max": 5000, "available_slots": [{"date": "2026-06-07", "start": "19:00", "end": "23:00"}], "category_prefs": ["restaurant"], "hard_constraints": []},
        {"budget_min": 3000, "budget_max": 6000, "available_slots": [{"date": "2026-06-07", "start": "19:00", "end": "23:00"}], "category_prefs": ["restaurant"], "hard_constraints": []},
        {"budget_min": 2500, "budget_max": 4000, "available_slots": [{"date": "2026-06-07", "start": "19:00", "end": "23:00"}], "category_prefs": ["restaurant", "bar"], "hard_constraints": []},
    ]
    spec = run_engine(prefs)

    assert spec.budget_target_cents > 0
    assert spec.pct_budget_satisfied == 1.0
    assert spec.pct_time_satisfied == 1.0
    assert spec.pct_prefs_satisfied > 0.5
    assert not spec.compromise_flagged
    assert spec.category == "restaurant"


def test_budget_no_overlap():
    prefs = [
        {"budget_min": 1000, "budget_max": 2000, "available_slots": [], "category_prefs": [], "hard_constraints": []},
        {"budget_min": 5000, "budget_max": 8000, "available_slots": [], "category_prefs": [], "hard_constraints": []},
    ]
    spec = run_engine(prefs)

    assert spec.compromise_flagged
    assert "overlap" in spec.compromise_explanation.lower()


def test_no_availability_overlap():
    prefs = [
        {"budget_min": 2000, "budget_max": 5000, "available_slots": [{"date": "2026-06-06", "start": "19:00", "end": "23:00"}], "category_prefs": ["concert"], "hard_constraints": []},
        {"budget_min": 2000, "budget_max": 5000, "available_slots": [{"date": "2026-06-07", "start": "19:00", "end": "23:00"}], "category_prefs": ["concert"], "hard_constraints": []},
    ]
    spec = run_engine(prefs)

    # Pas d'overlap → compromise flaggé car < 100% de la dispo satisfaite
    assert spec.pct_time_satisfied < 1.0


def test_hard_constraints_collected():
    prefs = [
        {"budget_min": 2000, "budget_max": 5000, "available_slots": [], "category_prefs": ["restaurant"], "hard_constraints": ["no_alcohol", "wheelchair"]},
        {"budget_min": 2000, "budget_max": 5000, "available_slots": [], "category_prefs": ["restaurant"], "hard_constraints": ["vegan"]},
    ]
    spec = run_engine(prefs)

    assert "no_alcohol" in spec.hard_constraints
    assert "wheelchair" in spec.hard_constraints
    assert "vegan" in spec.hard_constraints


def test_empty_preferences():
    spec = run_engine([])
    assert spec.compromise_flagged


def test_preference_parser_budget():
    from app.services.preference_parser import parse_budget

    assert parse_budget("20-50") == (2000, 5000)
    assert parse_budget("under 40") == (0, 4000)
    assert parse_budget("any") == (None, None)
    assert parse_budget("around 30")[0] < 3000
    assert parse_budget("around 30")[1] > 3000


def test_preference_parser_availability():
    from app.services.preference_parser import parse_availability

    slots = parse_availability("this saturday evening")
    assert len(slots) > 0
    assert all(s["start"] == "19:00" for s in slots)

    empty = parse_availability("any")
    assert empty == []
