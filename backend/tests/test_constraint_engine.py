"""Tests du constraint engine — pas de DB, testable sans infra."""
from app.services.constraint_engine import run_engine


def _pref(
    budget_min=2000, budget_max=5000,
    vibe=None, activity=None,
    departure_type="center", travel_time_max=30,
    hard_constraints=None,
    available_slots=None,
):
    """Helper pour construire une préférence de test."""
    return {
        "budget_min": budget_min,
        "budget_max": budget_max,
        "category_prefs": (vibe or []) + (activity or []),
        "hard_constraints": hard_constraints or [],
        "soft_preferences": vibe or [],
        "available_slots": available_slots or [],
        "raw_answers": {
            "vibe": vibe or [],
            "activity": activity or [],
            "departure_type": departure_type,
            "departure_text": None,
            "travel_time_max": travel_time_max,
        },
    }


def test_happy_path():
    prefs = [
        _pref(2000, 5000, vibe=["casual"], activity=["dinner"]),
        _pref(3000, 6000, vibe=["casual"], activity=["dinner"]),
        _pref(2500, 4000, vibe=["casual", "outdoor"], activity=["drinks"]),
    ]
    spec = run_engine(prefs)

    assert spec.vibe == "casual"
    assert spec.pct_budget_satisfied == 1.0
    assert spec.pct_prefs_satisfied > 0.5
    assert not spec.compromise_flagged
    assert spec.budget_target_cents > 0


def test_budget_no_overlap():
    prefs = [
        _pref(1000, 2000),
        _pref(5000, 8000),
    ]
    spec = run_engine(prefs)
    assert spec.compromise_flagged
    assert "overlap" in spec.compromise_explanation.lower()


def test_vibe_majority_vote():
    prefs = [
        _pref(vibe=["festive"]),
        _pref(vibe=["festive"]),
        _pref(vibe=["casual"]),
    ]
    spec = run_engine(prefs)
    assert spec.vibe == "festive"
    assert round(spec.pct_prefs_satisfied, 2) == round(2/3, 2)


def test_travel_time_median():
    prefs = [
        _pref(travel_time_max=15),
        _pref(travel_time_max=30),
        _pref(travel_time_max=45),
    ]
    spec = run_engine(prefs)
    assert spec.travel_time_max == 30


def test_travel_time_ignores_999():
    prefs = [
        _pref(travel_time_max=20),
        _pref(travel_time_max=999),  # "peu importe"
    ]
    spec = run_engine(prefs)
    assert spec.travel_time_max == 20


def test_location_departure_text():
    prefs = [
        {**_pref(), "raw_answers": {
            "vibe": [], "activity": [], "departure_type": "other",
            "departure_text": "Bastille", "travel_time_max": 30
        }},
        {**_pref(), "raw_answers": {
            "vibe": [], "activity": [], "departure_type": "other",
            "departure_text": "Bastille", "travel_time_max": 30
        }},
    ]
    spec = run_engine(prefs)
    assert spec.location_hint == "Bastille"


def test_location_departure_type_center():
    prefs = [_pref(departure_type="center"), _pref(departure_type="center")]
    spec = run_engine(prefs)
    assert "centre" in spec.location_hint.lower()


def test_hard_constraints_union():
    prefs = [
        _pref(hard_constraints=["no_alcohol", "wheelchair"]),
        _pref(hard_constraints=["halal"]),
    ]
    spec = run_engine(prefs)
    assert "no_alcohol" in spec.hard_constraints
    assert "wheelchair" in spec.hard_constraints
    assert "halal" in spec.hard_constraints


def test_empty_preferences():
    spec = run_engine([])
    assert spec.compromise_flagged


def test_title_generation():
    prefs = [_pref(vibe=["festive"], activity=["concert"])]
    spec = run_engine(prefs)
    assert "party" in spec.title.lower() or "festive" in spec.title.lower()
    assert "concert" in spec.title.lower()


def test_legitimacy_json_complete():
    prefs = [_pref(vibe=["cosy"], activity=["brunch"], travel_time_max=20)]
    spec = run_engine(prefs)
    j = spec.legitimacy_json
    assert "vibe" in j
    assert "activity" in j
    assert "location_hint" in j
    assert "travel_time_max_min" in j
    assert "budget_target_eur" in j
