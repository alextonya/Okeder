"""
Handler : mention @Okeder dans un groupe Telegram.
Crée l'event via le backend et démarre la collecte de contraintes.
"""
from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import backend_client
from bot.templates.messages import GROUP_INVOKED


async def handle_group_mention(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
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

        # 2. Enregistrer tous les membres connus du chat (best effort)
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

    if resp.status_code in (200, 201):
        data = resp.json()
        if data.get("existing"):
            await update.message.reply_text(
                "⚡ There's already an active event for this group!\n"
                "I'm still collecting preferences — stay tuned.",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(GROUP_INVOKED, parse_mode="HTML")
    else:
        await update.message.reply_text(
            "Something went wrong. Please try again or visit okeder.app"
        )


def _extract_title(text: str) -> str | None:
    clean = text.replace("@Okeder", "").strip()
    return clean if len(clean) > 3 else None
