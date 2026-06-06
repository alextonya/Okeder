"""
Tests des extracteurs heuristiques du handler @Okeder (handlers/group_invoke.py).

Quand un membre tape "@Okeder dîner à Bastille ce soir", ces fonctions devinent
le titre et le lieu (L1 — Intent Capture, Mode B). Régressions silencieuses ici
= events créés avec un mauvais titre/lieu.
"""
from bot.handlers.group_invoke import _extract_location, _extract_title


# ─── _extract_title ──────────────────────────────────────────────────────────

def test_title_strips_mention_and_keeps_text():
    assert _extract_title("@OkederBot dinner saturday") == "dinner saturday"


def test_title_too_short_returns_none():
    # "hi" fait 2 caractères (<= 3) → None
    assert _extract_title("@Okeder hi") is None


def test_title_only_mention_returns_none():
    assert _extract_title("@OkederBot") is None


# ─── _extract_location ───────────────────────────────────────────────────────

def test_location_english_in_pattern():
    assert _extract_location("@OkederBot dinner in London this weekend") == "London"


def test_location_french_a_pattern():
    assert _extract_location("@OkederBot dîner à Bastille ce soir") == "Bastille"


def test_location_near_pattern():
    assert _extract_location("@OkederBot dinner near the park on friday") == "The Park"


def test_location_none_when_no_pattern():
    assert _extract_location("@OkederBot dinner saturday") is None


def test_location_is_title_cased():
    # quel que soit la casse en entrée, sortie en Title Case
    assert _extract_location("@OkederBot lunch in paris on monday") == "Paris"
