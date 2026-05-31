"""
Handler : mention @Okeder dans un groupe Telegram.
Crée l'event et envoie un bouton Mini App pour collecter les préférences.
"""
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
        resp = await api.post(
            "/internal/telegram/create-event",
            json={
                "telegram_chat_id": chat.id,
                "title": _extract_title(update.message.text or ""),
                "wizard_mode": True,
            },
        )

    if resp.status_code not in (200, 201):
        await update.message.reply_text("Something went wrong. Please try again.")
        return

    data = resp.json()
    event_id = data.get("event_id", "")
    existing = data.get("existing", False)

    # URL publique du Mini App (ngrok en dev, domaine réel en prod)
    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")
    mini_app_url = f"{public_url}/mini-app/{event_id}"

    if existing:
        intro = "⚡ <b>There's already an active event!</b>\nStill collecting preferences:"
    else:
        intro = (
            "🎉 <b>Let's plan something!</b>\n\n"
            "Tap the button below to submit your preferences privately.\n"
            "Takes 30 seconds — no app needed."
        )

    # Bouton URL — ouvre le Mini App dans le navigateur
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📝 Submit my preferences →",
            url=mini_app_url,
        )
    ]])

    # Retry sur erreur TLS intermittente (Python 3.14 + anyio)
    import asyncio
    for attempt in range(3):
        try:
            await update.message.reply_text(intro, parse_mode="HTML", reply_markup=keyboard)
            break
        except Exception:
            if attempt < 2:
                await asyncio.sleep(0.5)
            else:
                raise


def _extract_title(text: str) -> str | None:
    clean = text.replace("@OkederBot", "").replace("@Okeder", "").strip()
    return clean if len(clean) > 3 else None
