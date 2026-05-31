"""
Handler : callbacks des boutons commitment (Interested / I'm In / Lock In).
Après chaque commitment → DM récapitulatif avec préférences + options.
"""
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from bot.api_client import backend_client
from bot.config import settings

LEVEL_LABELS = {
    "soft":      "👍 Interested",
    "confirmed": "✅ I'm In",
    "hard":      "🔒 Locked In",
}

ALL_LEVELS = [
    ("soft",      "👍 Interested"),
    ("confirmed", "✅ I'm In"),
    ("hard",      "🔒 Lock In"),
]


async def handle_commitment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """commit:{level}:{proposal_id}:{event_id}"""
    query = update.callback_query
    await query.answer()

    # Ignorer le bouton "current" (noop)
    if query.data == "noop":
        try:
            await query.answer(text="That's your current choice.", show_alert=False)
        except Exception:
            pass
        return

    parts = query.data.split(":")
    if len(parts) < 3:
        return

    _, level, proposal_id = parts[0], parts[1], parts[2]
    event_id = parts[3] if len(parts) > 3 else None
    user = query.from_user

    # 1. Toast immédiat — try/except car TLS intermittent sur Python 3.14
    label = LEVEL_LABELS.get(level, level)
    try:
        await query.answer(text=f"{label} — noted!", show_alert=False)
    except Exception:
        pass  # Toast non critique — on continue

    # 2. Enregistrer le commitment — le backend retourne l'event_id complet
    async with backend_client() as api:
        resp = await api.post(
            "/internal/telegram/commitment",
            json={
                "proposal_id": proposal_id,
                "level": level,
                "event_id": event_id or "",
                "telegram_user_id": user.id,
            },
        )

    resolved_event_id = event_id
    if resp and resp.status_code == 200:
        data = resp.json()
        resolved_event_id = data.get("event_id") or event_id
        resolved_proposal_id = data.get("proposal_id") or proposal_id
    else:
        resolved_proposal_id = proposal_id

    # 3. DM récapitulatif pour tous les niveaux (soft, confirmed, hard)
    if resolved_event_id:
        await _send_summary_dm(context, user.id, resolved_event_id, resolved_proposal_id, level)


async def _send_summary_dm(
    context,
    telegram_user_id: int,
    event_id: str,
    proposal_id: str,
    commitment_level: str,
) -> None:
    """Envoie un DM récapitulatif avec les préférences et options de modification."""
    async with backend_client() as api:
        resp = await api.get(
            "/internal/telegram/member-summary",
            params={"telegram_user_id": telegram_user_id, "event_id": event_id},
        )

    if not resp or resp.status_code != 200:
        return

    data = resp.json()
    if not data.get("found"):
        return

    prefs = data.get("preferences") or {}
    level_label = LEVEL_LABELS.get(commitment_level, commitment_level)

    # ─── Construction du message récapitulatif ────────────────────────────────
    lines = [
        f"{level_label} — here's your summary:",
        "",
    ]

    if prefs.get("vibe"):
        lines.append(f"🎭 Vibe: {', '.join(prefs['vibe'])}")
    if prefs.get("activity"):
        lines.append(f"🍽️ Activity: {', '.join(prefs['activity'])}")
    if prefs.get("departure_text"):
        lines.append(f"📍 Zone: {prefs['departure_text']}")
    if prefs.get("travel_time_max") and prefs["travel_time_max"] != 999:
        lines.append(f"⏱️ Travel: {prefs['travel_time_max']} min max")
    if prefs.get("budget_min") or prefs.get("budget_max"):
        b_min = f"€{prefs['budget_min']//100}" if prefs.get("budget_min") else "?"
        b_max = f"€{prefs['budget_max']//100}" if prefs.get("budget_max") else "?"
        lines.append(f"💶 Budget: {b_min} – {b_max}")
    if prefs.get("hard_constraints"):
        lines.append(f"🚫 Hard nos: {', '.join(prefs['hard_constraints'])}")

    if not prefs:
        lines.append("No preferences submitted yet.")

    lines.extend(["", "Want to update anything?"])

    text = "\n".join(lines)

    # ─── Boutons ──────────────────────────────────────────────────────────────
    keyboard_rows = []

    # Les 3 niveaux — le niveau actuel est marqué d'une coche
    p_short = proposal_id.replace("-", "")[:12]
    e_short = event_id.replace("-", "")[:12] if event_id else "000000000000"
    for alt_level, alt_label in ALL_LEVELS:
        if alt_level == commitment_level:
            # Niveau actuel — bouton désactivé avec coche
            keyboard_rows.append([
                InlineKeyboardButton(f"✓ {alt_label} (current)", callback_data="noop")
            ])
        else:
            keyboard_rows.append([
                InlineKeyboardButton(
                    f"Change to {alt_label}",
                    callback_data=f"commit:{alt_level}:{p_short}:{e_short}",
                )
            ])

    # Bouton "Modifier" — WebAppInfo en DM = initData disponible = préremplissage
    public_url = os.environ.get("PUBLIC_URL", "")
    if public_url and public_url.startswith("https://") and event_id:
        mini_app_url = f"{public_url}/mini-app/{event_id}"
        keyboard_rows.insert(0, [
            InlineKeyboardButton(
                "✏️ Modify my preferences",
                web_app=WebAppInfo(url=mini_app_url),
            )
        ])

    # Construire le keyboard dict pour urllib
    keyboard_dict = {"inline_keyboard": [
        [{"text": btn.text, "callback_data": btn.callback_data}
         if btn.callback_data else
         {"text": btn.text, "web_app": {"url": btn.web_app.url}}
         for btn in row]
        for row in keyboard_rows
    ]}

    from bot.telegram_utils import send_message as _send
    await _send(chat_id=telegram_user_id, text=text, reply_markup=keyboard_dict)
