"""
Parse les réponses texte brutes du bot Telegram en données structurées.
Tolérant par design : préfère ne rien stocker plutôt que stocker faux.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone


def parse_budget(raw: str) -> tuple[int | None, int | None]:
    """
    '20-50' → (2000, 5000)
    'under 40' / 'less than 40' → (0, 4000)
    'around 30' → (2000, 4000)
    'any' / 'no preference' → (None, None)
    """
    raw = raw.strip().lower()
    if not raw or raw in ("any", "no preference", "flexible", "doesn't matter"):
        return None, None

    # Plage explicite : 20-50, 20 to 50, 20/50
    m = re.search(r"(\d+)\s*[-–to/]+\s*(\d+)", raw)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return min(lo, hi) * 100, max(lo, hi) * 100

    # Plafond : under/less than/max/up to N
    m = re.search(r"(?:under|less than|max|up to|<)\s*(\d+)", raw)
    if m:
        return 0, int(m.group(1)) * 100

    # Plancher : over/more than/at least N
    m = re.search(r"(?:over|more than|at least|>)\s*(\d+)", raw)
    if m:
        n = int(m.group(1)) * 100
        return n, n * 3  # plage raisonnable

    # Valeur unique : around/about/~N ou juste N
    m = re.search(r"(?:around|about|~|circa)?\s*(\d+)", raw)
    if m:
        n = int(m.group(1)) * 100
        margin = int(n * 0.3)
        return max(0, n - margin), n + margin

    return None, None


def parse_availability(raw: str) -> list[dict]:
    """
    Parse un texte de disponibilité en slots [{date, start, end}].
    Retourne une liste de slots best-effort — peut être vide si non parsable.
    """
    raw = raw.strip().lower()
    if not raw or raw in ("any", "anytime", "flexible", "whenever"):
        return []  # pas de contrainte de dispo = tous les slots sont OK

    now = datetime.now(timezone.utc)
    slots = []

    # Détection de jours de semaine
    day_map = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6,
    }

    mentioned_days = [d for name, d in day_map.items() if name in raw]

    # Qualificateurs temporels
    is_next_week = "next week" in raw or "next 2 weeks" in raw
    is_weekend = "weekend" in raw
    is_evening = "evening" in raw or "night" in raw or "dinner" in raw

    if is_weekend:
        mentioned_days = list(set(mentioned_days) | {5, 6})  # sat + sun

    horizon_days = 14 if is_next_week else 7

    for day_offset in range(1, horizon_days + 1):
        candidate = now + timedelta(days=day_offset)
        if not mentioned_days or candidate.weekday() in mentioned_days:
            start_hour = "19:00" if is_evening else "10:00"
            end_hour = "23:00" if is_evening else "22:00"
            slots.append({
                "date": candidate.strftime("%Y-%m-%d"),
                "start": start_hour,
                "end": end_hour,
            })

    return slots[:10]  # limiter à 10 slots max
