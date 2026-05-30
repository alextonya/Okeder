"""
Handler : callbacks des boutons commitment (Soft / Confirm / Hard).
"""
import httpx
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import settings


async def handle_commitment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """commit:{level}:{proposal_id}"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, level, proposal_id = parts
    user = query.from_user

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.backend_api_url}/internal/telegram/commitment",
            json={
                "proposal_id": proposal_id,
                "level": level,
                "telegram_user_id": user.id,
            },
        )

    if level == "hard":
        # Deeplink vers la PWA pour le paiement Stripe
        pwa_url = f"https://okeder.app/events/commit?proposal={proposal_id}"
        await query.answer(
            text=f"To lock in with payment, open: {pwa_url}",
            show_alert=True,
        )
    else:
        level_label = {"soft": "👍 Interested", "confirmed": "✅ I'm In"}.get(level, level)
        await query.answer(text=f"Noted: {level_label}", show_alert=False)
