"""
Tests du scoring de lieux (services/overpass_service.py).

Couche L6 (Execution) — sélection du meilleur lieu OpenStreetMap.
Score = 0.40·distance + 0.25·type + 0.20·complétude + 0.15·équité,
avec élimination ÉLIMINATOIRE des hard constraints (score = 0).

La règle critique testée ici : une contrainte "no alcohol" DOIT écarter
les bars/pubs — un faux négatif enverrait un groupe sobre dans un bar.
"""
import math

from app.services.overpass_service import _haversine, _score_venue

# Coordonnées de référence (centre de Paris)
PARIS = (48.8566, 2.3522)


# ─── _haversine ──────────────────────────────────────────────────────────────

def test_haversine_same_point_is_zero():
    assert _haversine(*PARIS, *PARIS) == 0.0


def test_haversine_symmetric():
    a = _haversine(48.85, 2.35, 48.90, 2.40)
    b = _haversine(48.90, 2.40, 48.85, 2.35)
    assert math.isclose(a, b, rel_tol=1e-9)


def test_haversine_one_degree_latitude_is_about_111km():
    d = _haversine(0.0, 0.0, 1.0, 0.0)
    assert 110 < d < 112  # ~111.19 km


# ─── _score_venue : hard constraints éliminatoires ───────────────────────────

def _venue(name="Chez Test", category="restaurant", lat=48.8566, lng=2.3522,
           address="1 rue de Test"):
    return {"name": name, "category": category, "lat": lat, "lng": lng,
            "address": address}


def test_no_alcohol_eliminates_bar_by_category():
    score = _score_venue(
        _venue(name="Le Resto", category="bar"),
        member_coords=[PARIS],
        activity="dinner", vibe="casual",
        hard_constraints=["no alcohol"],
        radius_km=5.0,
    )
    assert score == 0.0


def test_no_alcohol_underscore_variant_also_eliminates():
    score = _score_venue(
        _venue(name="The Old Pub", category="restaurant"),  # "pub" dans le nom
        member_coords=[PARIS],
        activity="dinner", vibe="casual",
        hard_constraints=["no_alcohol"],
        radius_km=5.0,
    )
    assert score == 0.0


def test_no_alcohol_keeps_a_clean_restaurant():
    score = _score_venue(
        _venue(name="Le Bistrot Vert", category="restaurant"),
        member_coords=[PARIS],
        activity="dinner", vibe="casual",
        hard_constraints=["no alcohol"],
        radius_km=5.0,
    )
    assert score > 0.0


def test_unknown_constraint_does_not_eliminate():
    # une contrainte inconnue (non mappée) ne doit pas mettre le score à 0
    score = _score_venue(
        _venue(category="bar"),
        member_coords=[PARIS],
        activity="drinks", vibe="festive",
        hard_constraints=["wheelchair"],
        radius_km=5.0,
    )
    assert score > 0.0


# ─── _score_venue : bornes et monotonie ──────────────────────────────────────

def test_score_within_unit_range():
    score = _score_venue(
        _venue(), member_coords=[PARIS],
        activity="dinner", vibe="casual",
        hard_constraints=[], radius_km=5.0,
    )
    assert 0.0 <= score <= 1.0


def test_closer_venue_scores_higher_than_far_one():
    near = _venue(name="Near", category="restaurant", lat=48.8570, lng=2.3525)
    far = _venue(name="Far", category="restaurant", lat=49.20, lng=2.80)
    s_near = _score_venue(near, [PARIS], "dinner", "casual", [], 5.0)
    s_far = _score_venue(far, [PARIS], "dinner", "casual", [], 5.0)
    assert s_near > s_far


def test_type_match_boosts_score():
    matching = _venue(name="Pizzeria Italian", category="restaurant")
    mismatch = _venue(name="Random Place", category="bank")
    s_match = _score_venue(matching, [PARIS], "dinner", "casual", [], 5.0)
    s_mismatch = _score_venue(mismatch, [PARIS], "dinner", "casual", [], 5.0)
    assert s_match > s_mismatch


def test_completeness_boosts_score():
    complete = _venue(name="Full Resto", category="restaurant", address="10 rue X")
    sparse = {"name": "", "category": "restaurant", "lat": None, "lng": None,
              "address": None}
    s_complete = _score_venue(complete, [PARIS], "dinner", "casual", [], 5.0)
    s_sparse = _score_venue(sparse, [], "dinner", "casual", [], 5.0)
    assert s_complete > s_sparse
