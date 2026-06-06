"""
Tests du parseur de préférences (services/preference_parser.py).

Ce module convertit le texte libre saisi par les membres dans le bot Telegram
(L2 — Constraint Collection) en données structurées (budget en centimes, slots
de disponibilité). C'est le point d'entrée des données réelles : si le parsing
dérive, tout le moteur d'arbitrage (L3) reçoit des entrées fausses.

Les assertions reflètent le COMPORTEMENT RÉEL du code (la docstring du module
est approximative — ex. "around 30" donne en réalité (2100, 3900), pas
(2000, 4000)).
"""
from app.services.preference_parser import parse_availability, parse_budget


# ─── parse_budget ────────────────────────────────────────────────────────────

def test_budget_explicit_range():
    assert parse_budget("20-50") == (2000, 5000)


def test_budget_range_with_words_and_slash():
    assert parse_budget("20 to 50") == (2000, 5000)
    assert parse_budget("20/50") == (2000, 5000)


def test_budget_range_is_normalized_low_high():
    # saisie inversée : doit ressortir (min, max)
    assert parse_budget("50-20") == (2000, 5000)


def test_budget_ceiling():
    assert parse_budget("under 40") == (0, 4000)
    assert parse_budget("less than 40") == (0, 4000)
    assert parse_budget("max 40") == (0, 4000)
    assert parse_budget("< 40") == (0, 4000)


def test_budget_floor_expands_to_3x():
    # "over 50" → plancher 5000, plafond raisonnable = 3x
    assert parse_budget("over 50") == (5000, 15000)
    assert parse_budget("at least 50") == (5000, 15000)


def test_budget_single_value_uses_30pct_margin():
    # n=3000, marge = 30% = 900 → (2100, 3900)
    assert parse_budget("around 30") == (2100, 3900)
    assert parse_budget("30") == (2100, 3900)


def test_budget_none_keywords():
    for raw in ("any", "no preference", "flexible", "doesn't matter", ""):
        assert parse_budget(raw) == (None, None)


def test_budget_unparsable_returns_none():
    assert parse_budget("whatever works for everyone") == (None, None)


def test_budget_is_case_and_space_insensitive():
    assert parse_budget("  UNDER 40  ") == (0, 4000)


def test_budget_returns_cents_not_euros():
    lo, hi = parse_budget("20-50")
    assert (lo, hi) == (2000, 5000)  # centimes, pas euros


# ─── parse_availability ──────────────────────────────────────────────────────

def test_availability_anytime_means_no_constraint():
    for raw in ("any", "anytime", "flexible", "whenever", ""):
        assert parse_availability(raw) == []


def test_availability_single_weekday_only_that_day():
    slots = parse_availability("saturday")
    assert slots, "au moins un slot attendu"
    # 5 = samedi (lundi=0)
    for s in slots:
        from datetime import datetime
        wd = datetime.strptime(s["date"], "%Y-%m-%d").weekday()
        assert wd == 5


def test_availability_evening_sets_evening_hours():
    slots = parse_availability("friday evening")
    assert slots
    for s in slots:
        assert s["start"] == "19:00"
        assert s["end"] == "23:00"


def test_availability_daytime_default_hours():
    slots = parse_availability("saturday")
    for s in slots:
        assert s["start"] == "10:00"
        assert s["end"] == "22:00"


def test_availability_weekend_expands_to_sat_sun():
    slots = parse_availability("weekend")
    assert slots
    from datetime import datetime
    weekdays = {datetime.strptime(s["date"], "%Y-%m-%d").weekday() for s in slots}
    assert weekdays <= {5, 6}
    assert weekdays  # non vide


def test_availability_capped_at_10_slots():
    # "next week" sans jour précis → horizon 14 jours, mais plafonné à 10
    slots = parse_availability("next week")
    assert len(slots) <= 10


def test_availability_slot_shape():
    slots = parse_availability("monday")
    assert slots
    for s in slots:
        assert set(s.keys()) == {"date", "start", "end"}
