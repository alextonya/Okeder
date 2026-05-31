"""
L3 — Constraint Engine : intersection pondérée des préférences du groupe.

Champs exploités depuis raw_answers :
  vibe            : ambiance souhaitée (casual, professional, festive, cosy, outdoor, cultural)
  activity        : type d'activité (dinner, drinks, concert, activity, cinema, brunch)
  departure_type  : home | work | center | other
  departure_text  : texte libre si departure_type = other
  travel_time_max : int (minutes)
  budget_min/max  : int (EUR cents)
  hard_constraints: list[str]
"""
from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProposalSpec:
    title: str = ""
    category: str = ""          # activité principale
    vibe: str = ""              # ambiance principale
    budget_target_cents: int = 0
    travel_time_max: int = 30   # minutes, médiane du groupe
    location_hint: str = ""     # zone géographique déduite
    best_day: str = ""
    best_time: str = ""
    datetime_hint: str = ""
    midpoint_lat: float | None = None   # midpoint géographique
    midpoint_lng: float | None = None
    hard_constraints: list[str] = field(default_factory=list)

    pct_budget_satisfied: float = 0.0
    pct_time_satisfied: float = 0.0
    pct_prefs_satisfied: float = 0.0
    hard_constraints_met: bool = True
    compromise_flagged: bool = False
    compromise_explanation: str = ""
    legitimacy_json: dict[str, Any] = field(default_factory=dict)


def run_engine(preferences: list[dict[str, Any]]) -> ProposalSpec:
    """
    preferences : liste de dicts avec les colonnes Preference + raw_answers.
    Retourne un ProposalSpec avec toutes les métriques de légitimité.
    """
    if not preferences:
        return ProposalSpec(
            compromise_flagged=True,
            compromise_explanation="No preferences submitted yet"
        )

    spec = ProposalSpec()

    # Extraire raw_answers pour les nouveaux champs
    raw_list = [p.get("raw_answers") or {} for p in preferences]

    # ─── 1. Budget ────────────────────────────────────────────────────────────
    mins = [p["budget_min"] for p in preferences if p.get("budget_min") is not None]
    maxs = [p["budget_max"] for p in preferences if p.get("budget_max") is not None]

    if mins and maxs:
        budget_min = max(mins)
        budget_max = min(maxs)
        if budget_min <= budget_max:
            spec.budget_target_cents = (budget_min + budget_max) // 2
        else:
            spec.budget_target_cents = int(statistics.median(maxs))
            spec.compromise_flagged = True
            spec.compromise_explanation = "Budget ranges don't overlap — using median of upper bounds"
    elif maxs:
        spec.budget_target_cents = int(statistics.median(maxs))

    satisfied_budget = sum(
        1 for p in preferences
        if p.get("budget_max") and p["budget_max"] >= spec.budget_target_cents
    )
    spec.pct_budget_satisfied = satisfied_budget / len(preferences) if preferences else 0.0

    # ─── 2. Vibe (ambiance) ───────────────────────────────────────────────────
    all_vibes: list[str] = []
    for r in raw_list:
        all_vibes.extend(r.get("vibe") or [])

    if all_vibes:
        vibe_counts = Counter(all_vibes)
        spec.vibe = vibe_counts.most_common(1)[0][0]
        top_vibe_count = vibe_counts[spec.vibe]
        spec.pct_prefs_satisfied = top_vibe_count / len(preferences)
    else:
        # Fallback sur category_prefs (ancien format bot DM)
        cats: list[str] = []
        for p in preferences:
            cats.extend(p.get("category_prefs") or [])
        if cats:
            cat_counts = Counter(cats)
            spec.vibe = cat_counts.most_common(1)[0][0]
            spec.pct_prefs_satisfied = cat_counts[spec.vibe] / len(preferences)

    # ─── 3. Activité ──────────────────────────────────────────────────────────
    all_activities: list[str] = []
    for r in raw_list:
        all_activities.extend(r.get("activity") or [])

    if all_activities:
        act_counts = Counter(all_activities)
        spec.category = act_counts.most_common(1)[0][0]
    else:
        spec.category = spec.vibe  # fallback

    # ─── 4. Temps de trajet ───────────────────────────────────────────────────
    travel_times = [
        r.get("travel_time_max") for r in raw_list
        if r.get("travel_time_max") and r["travel_time_max"] != 999
    ]
    if travel_times:
        spec.travel_time_max = int(statistics.median(travel_times))
    else:
        spec.travel_time_max = 30  # défaut 30 min

    # ─── 5. Zone géographique ─────────────────────────────────────────────────
    # Ordre de priorité : departure_text > departure_type
    departure_texts = [
        r.get("departure_text") for r in raw_list
        if r.get("departure_text")
    ]
    departure_types = [
        r.get("departure_type") for r in raw_list
        if r.get("departure_type")
    ]

    # Essayer de calculer le midpoint géographique depuis les coordonnées
    coords = [
        (r.get("departure_lat"), r.get("departure_lng"))
        for r in raw_list
        if r.get("departure_lat") and r.get("departure_lng")
    ]

    if coords:
        # Midpoint = moyenne des lat/lng
        mid_lat = sum(c[0] for c in coords) / len(coords)
        mid_lng = sum(c[1] for c in coords) / len(coords)
        spec.midpoint_lat = mid_lat
        spec.midpoint_lng = mid_lng
        # Texte de fallback depuis les noms
        if departure_texts:
            spec.location_hint = departure_texts[0]
        else:
            spec.location_hint = f"{mid_lat:.4f},{mid_lng:.4f}"
    elif departure_texts:
        type_counts = Counter(departure_texts)
        spec.location_hint = type_counts.most_common(1)[0][0]
    elif departure_types:
        type_counts = Counter(departure_types)
        most_common_type = type_counts.most_common(1)[0][0]
        spec.location_hint = {
            "home": "Near members' homes",
            "work": "Near the office",
            "center": "City centre",
            "other": "To be determined",
        }.get(most_common_type, "City centre")
    else:
        spec.location_hint = "City centre"

    # ─── 6. Hard constraints (union) ──────────────────────────────────────────
    all_hard: set[str] = set()
    for p in preferences:
        all_hard.update(p.get("hard_constraints") or [])
    spec.hard_constraints = list(all_hard)

    # ─── 7. Temps de dispo (best slot commun) ─────────────────────────────────
    slot_scores: dict[str, int] = {}
    for p in preferences:
        for slot in (p.get("available_slots") or []):
            key = f"{slot.get('date')}_{slot.get('start')}"
            slot_scores[key] = slot_scores.get(key, 0) + 1

    if slot_scores:
        best_count = max(slot_scores.values())
        spec.pct_time_satisfied = best_count / len(preferences)
        if spec.pct_time_satisfied < 1.0:
            spec.compromise_flagged = True
    else:
        spec.pct_time_satisfied = 0.5  # pas de slots renseignés → neutre

    # ─── 8. Flags compromise global ───────────────────────────────────────────
    if spec.pct_budget_satisfied < 0.70:
        spec.compromise_flagged = True
        if not spec.compromise_explanation:
            spec.compromise_explanation = "Budget ranges partially overlap"

    # ─── 9. Titre et bloc légitimité ──────────────────────────────────────────
    vibe_labels = {
        "casual": "Casual outing",
        "professional": "Team event",
        "festive": "Party night",
        "cosy": "Cosy evening",
        "outdoor": "Outdoor activity",
        "cultural": "Cultural outing",
    }
    act_labels = {
        "dinner": "dinner",
        "drinks": "drinks",
        "concert": "concert",
        "activity": "activity",
        "cinema": "cinema",
        "brunch": "brunch",
    }
    vibe_label = vibe_labels.get(spec.vibe, spec.vibe.capitalize())
    act_label  = act_labels.get(spec.category, spec.category)
    spec.title = f"{vibe_label} — {act_label}" if spec.category != spec.vibe else vibe_label

    # ─── 8. Date préférée + marge ─────────────────────────────────────────────
    from datetime import datetime, timedelta

    all_times: list[str] = []
    dates_with_margin: list[tuple] = []  # (preferred_date, margin_days)

    for r in raw_list:
        all_times.extend(r.get("times") or [])
        d = r.get("preferred_date")
        m = r.get("date_margin_days") or 5
        if d:
            try:
                dates_with_margin.append((datetime.fromisoformat(d).date(), int(m)))
            except ValueError:
                pass

    time_labels = {
        "lunch":      "lunchtime",
        "after_work": "after work",
        "evening":    "evening",
        "weekend":    "over the weekend",
    }

    if all_times:
        time_counts = Counter(all_times)
        spec.best_time = time_counts.most_common(1)[0][0]
    time_str = time_labels.get(spec.best_time, spec.best_time) if spec.best_time else ""

    # Trouver la plage de dates commune (intersection des fenêtres)
    if dates_with_margin:
        # Chaque membre a une fenêtre [date - margin, date + margin]
        # Intersection = [max des starts, min des ends]
        windows = [(d - timedelta(days=m), d + timedelta(days=m)) for d, m in dates_with_margin]
        common_start = max(w[0] for w in windows)
        common_end = min(w[1] for w in windows)

        if common_start <= common_end:
            mid_date = common_start + (common_end - common_start) // 2
            spec.best_day = mid_date.strftime("%A").lower()
        else:
            spec.compromise_flagged = True
            spec.compromise_explanation = "No common date window — using median date"
            all_dates = sorted(d for d, _ in dates_with_margin)
            mid_date = all_dates[len(all_dates) // 2]

        # Date lisible + ISO pour le lien calendrier
        hour = {"lunch": 12, "after_work": 18, "evening": 19, "weekend": 14}.get(spec.best_time, 19)
        spec.legitimacy_json["proposed_date_iso"] = mid_date.isoformat()
        spec.legitimacy_json["proposed_hour"] = hour
        date_str = mid_date.strftime("%A %d %B")
        spec.datetime_hint = f"{date_str}{', ' + time_str if time_str else ''}"
    elif time_str:
        spec.datetime_hint = time_str.capitalize()
    else:
        spec.datetime_hint = "TBD"

    spec.legitimacy_json = {
        "vibe":                  spec.vibe,
        "activity":              spec.category,
        "location_hint":         spec.location_hint,
        "datetime_hint":         spec.datetime_hint or "TBD",
        "travel_time_max_min":   spec.travel_time_max,
        "budget_target_eur":     round(spec.budget_target_cents / 100, 2),
        "hard_constraints":      spec.hard_constraints,
        "pct_budget_satisfied":  round(spec.pct_budget_satisfied * 100, 1),
        "pct_time_satisfied":    round(spec.pct_time_satisfied * 100, 1),
        "pct_prefs_satisfied":   round(spec.pct_prefs_satisfied * 100, 1),
        "compromise_flagged":    spec.compromise_flagged,
        "compromise_explanation": spec.compromise_explanation,
    }

    return spec
