"""
L3 — Constraint Engine : intersection pondérée des préférences du groupe.
Retourne une ProposalSpec (pas encore un objet DB) avec le bloc de légitimité L4.

Séquence :
1. Budget : intersection [max(mins), min(maxs)] → si invalide, médiane + flag compromise
2. Disponibilité : intersection des slots → si vide, slot satisfaisant le plus de membres
3. Catégorie : score pondéré (poids = 1.0 en MVP, profil comportemental à M6+)
4. Hard constraints : union — aucune option ne peut violer une seule
5. Légitimité : calcul pct_satisfied par dimension, compromise_flagged si < 70%
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProposalSpec:
    title: str = ""
    category: str = ""
    budget_target_cents: int = 0
    available_slot: dict[str, Any] = field(default_factory=dict)
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
    preferences: liste de dicts correspondant aux colonnes de la table Preference.
    Retourne un ProposalSpec avec toutes les métriques de légitimité calculées.
    """
    if not preferences:
        return ProposalSpec(compromise_flagged=True, compromise_explanation="No preferences submitted")

    spec = ProposalSpec()

    # 1. Budget
    mins = [p["budget_min"] for p in preferences if p.get("budget_min") is not None]
    maxs = [p["budget_max"] for p in preferences if p.get("budget_max") is not None]
    if mins and maxs:
        budget_min = max(mins)
        budget_max = min(maxs)
        if budget_min <= budget_max:
            spec.budget_target_cents = (budget_min + budget_max) // 2
        else:
            # Compromise : médiane de tous les maxima
            spec.budget_target_cents = int(statistics.median(maxs))
            spec.compromise_flagged = True
            spec.compromise_explanation = "Budget ranges don't overlap — using median of upper bounds"

    satisfied_budget = sum(
        1 for p in preferences
        if p.get("budget_max") and p["budget_max"] >= spec.budget_target_cents
    )
    spec.pct_budget_satisfied = satisfied_budget / len(preferences)

    # 2. Disponibilité — simplifié MVP : trouve le slot avec le plus de membres disponibles
    slot_scores: dict[str, int] = {}
    for p in preferences:
        for slot in (p.get("available_slots") or []):
            key = f"{slot.get('date')}_{slot.get('start')}"
            slot_scores[key] = slot_scores.get(key, 0) + 1

    if slot_scores:
        best_slot_key = max(slot_scores, key=lambda k: slot_scores[k])
        best_count = slot_scores[best_slot_key]
        spec.available_slot = {"key": best_slot_key}
        spec.pct_time_satisfied = best_count / len(preferences)
        if spec.pct_time_satisfied < 1.0:
            spec.compromise_flagged = True
    else:
        spec.pct_time_satisfied = 0.0
        spec.compromise_flagged = True

    # 3. Catégorie — score pondéré (poids = 1.0 MVP)
    category_scores: dict[str, float] = {}
    for p in preferences:
        for cat in (p.get("category_prefs") or []):
            category_scores[cat] = category_scores.get(cat, 0.0) + 1.0

    if category_scores:
        spec.category = max(category_scores, key=lambda k: category_scores[k])
        top_score = category_scores[spec.category]
        spec.pct_prefs_satisfied = top_score / len(preferences)
    else:
        spec.pct_prefs_satisfied = 0.0

    # 4. Hard constraints — union
    all_hard: set[str] = set()
    for p in preferences:
        all_hard.update(p.get("hard_constraints") or [])
    spec.hard_constraints = list(all_hard)

    # 5. Flag compromise global
    if spec.pct_budget_satisfied < 0.70 or spec.pct_time_satisfied < 0.70:
        spec.compromise_flagged = True

    spec.title = f"{spec.category.capitalize()} outing" if spec.category else "Group outing"

    spec.legitimacy_json = {
        "pct_budget_satisfied": round(spec.pct_budget_satisfied * 100, 1),
        "pct_time_satisfied": round(spec.pct_time_satisfied * 100, 1),
        "pct_prefs_satisfied": round(spec.pct_prefs_satisfied * 100, 1),
        "hard_constraints": spec.hard_constraints,
        "compromise_flagged": spec.compromise_flagged,
        "compromise_explanation": spec.compromise_explanation,
    }

    return spec
