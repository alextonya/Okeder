from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import backend_client


async def handle_commitment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """commit:{level}:{proposal_id}"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, level, proposal_id = parts

    async with backend_client() as api:
        await api.post(
            "/internal/telegram/commitment",
            json={
                "proposal_id": proposal_id,
                "level": level,
                "telegram_user_id": query.from_user.id,
            },
        )

    if level == "hard":
        pwa_url = f"{_pwa_url()}/events/commit?proposal={proposal_id}"
        await query.answer(
            text=f"To lock in with payment: {pwa_url}",
            show_alert=True,
        )
    else:
        label = {"soft": "👍 Interested — noted!", "confirmed": "✅ You're in!"}.get(level, level)
        await query.answer(text=label, show_alert=False)


def _pwa_url() -> str:
    from bot.config import settings
    # settings.backend_api_url est http://backend:8000/v1 → on reconstruit l'URL PWA
    return "https://okeder.app"
