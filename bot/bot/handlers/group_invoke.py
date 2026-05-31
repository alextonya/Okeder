"""
Handler : mention @Okeder dans un groupe Telegram.
Crée l'event et envoie un bouton Mini App pour collecter les préférences.
"""
import os

from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import backend_client
from bot.config import settings


async def handle_group_mention(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    # Vérifie que le message mentionne le bot (insensible à la casse)
    text = update.message.text or ""
    bot_username = settings.telegram_bot_username or "OkederBot"
    if f"@{bot_username}".lower() not in text.lower():
        return

    chat = update.effective_chat
    user = update.effective_user

    async with backend_client() as api:
        # 1. Enregistrer le groupe et l'initiateur
        await api.post(
            "/internal/telegram/register-group",
            json={
                "telegram_chat_id": chat.id,
                "chat_title": chat.title or "Group",
                "initiator_telegram_id": user.id if user else None,
                "initiator_name": user.full_name if user else "Unknown",
            },
        )

        # 2. Enregistrer l'initiateur
        if user:
            await api.post(
                "/internal/telegram/register-member",
                json={
                    "telegram_user_id": user.id,
                    "display_name": user.full_name,
                    "telegram_chat_id": chat.id,
                },
            )

        # 3. Créer l'event
        msg_text = update.message.text or ""
        resp = await api.post(
            "/internal/telegram/create-event",
            json={
                "telegram_chat_id": chat.id,
                "title": _extract_title(msg_text),
                "location": _extract_location(msg_text),
                "wizard_mode": False,  # Auto par défaut
            },
        )

    if resp.status_code not in (200, 201):
        await update.message.reply_text("Something went wrong. Please try again.")
        return

    data = resp.json()
    event_id = data.get("event_id", "")

    # Deep link vers le bot en DM — le bot y enverra le bouton WebApp
    bot_username = settings.telegram_bot_username or "OkederBot"
    deep_link = f"https://t.me/{bot_username}?start=event_{event_id}"

    intro = (
        "🎉 <b>Let's plan something!</b>\n\n"
        "Tap the button below to submit your preferences privately.\n"
        "Takes 30 seconds — no app needed."
    )

    # Bouton deep link → ouvre le bot en DM → le bot envoie le WebApp
    # Utilise urllib (pas httpx) pour éviter le bug TLS anyio/Python 3.14
    from bot.telegram_utils import send_message as _send

    keyboard_dict = {
        "inline_keyboard": [[
            {"text": "📝 Submit my preferences →", "url": deep_link}
        ]]
    }
    await _send(
        chat_id=update.effective_chat.id,
        text=intro,
        reply_markup=keyboard_dict,
    )


def _extract_title(text: str) -> str | None:
    clean = text.replace("@OkederBot", "").replace("@Okeder", "").strip()
    return clean if len(clean) > 3 else None


def _extract_location(text: str) -> str | None:
    """
    Extrait la localisation du message d'invocation.
    Exemples :
      "@OkederBot sortie à Paris" → "Paris"
      "@OkederBot dinner in London" → "London"
      "@OkederBot on sort à Bastille ce soir" → "Bastille"
    """
    import re
    clean = text.replace("@OkederBot", "").replace("@Okeder", "").strip()

    # Patterns FR et EN
    patterns = [
        r"\bà\s+([A-ZÀ-Ÿa-zà-ÿ][A-Za-zÀ-ÿ\s\-]{1,30}?)(?:\s+ce|\s+cette|\s+le|\s+la|\s*$)",
        r"\bin\s+([A-Z][A-Za-z\s\-]{1,30}?)(?:\s+this|\s+on|\s*$)",
        r"\bnear\s+([A-Za-z\s\-]{2,30}?)(?:\s+this|\s+on|\s*$)",
        r"\bprès\s+de\s+([A-ZÀ-Ÿa-zà-ÿ][A-Za-zÀ-ÿ\s\-]{1,30}?)(?:\s|\s*$)",
    ]

    for pattern in patterns:
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            loc = m.group(1).strip().rstrip(".,!")
            if len(loc) >= 2:
                return loc.title()

    return None
