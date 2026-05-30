from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import backend_client
from bot.templates.messages import RATING_THANKS


async def handle_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """rate:{score}:{event_id}"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, score, event_id = parts

    async with backend_client() as api:
        await api.post(
            "/internal/telegram/rating",
            json={
                "event_id": event_id,
                "score": int(score),
                "telegram_user_id": query.from_user.id,
            },
        )

    await query.edit_message_text(RATING_THANKS, parse_mode="HTML")
