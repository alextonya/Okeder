"""
Handler : mention @Okeder dans un groupe Telegram.
Crée l'event via l'API backend et démarre la collecte de contraintes.
"""
import httpx
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import settings
from bot.templates.messages import GROUP_INVOKED


async def handle_group_mention(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Déclenché quand @Okeder est mentionné dans un groupe."""
    if not update.message or not update.effective_chat:
        return

    chat = update.effective_chat
    user = update.effective_user

    # Récupérer ou créer l'event via le backend
    async with httpx.AsyncClient() as client:
        # Enregistrer le membre initiateur si nécessaire
        await client.post(
            f"{settings.backend_api_url}/internal/telegram/register-group",
            json={
                "telegram_chat_id": chat.id,
                "chat_title": chat.title or "Group",
                "initiator_telegram_id": user.id if user else None,
                "initiator_name": user.full_name if user else "Unknown",
            },
        )

        # Créer l'event
        resp = await client.post(
            f"{settings.backend_api_url}/internal/telegram/create-event",
            json={
                "telegram_chat_id": chat.id,
                "title": _extract_title(update.message.text or ""),
                "wizard_mode": True,
            },
        )

    if resp.status_code == 201:
        await update.message.reply_text(GROUP_INVOKED, parse_mode="HTML")
    else:
        await update.message.reply_text(
            "Something went wrong. Please try again or visit okeder.app"
        )


def _extract_title(text: str) -> str | None:
    """Extrait un titre optionnel du message d'invocation."""
    clean = text.replace("@Okeder", "").strip()
    return clean if len(clean) > 3 else None
