"""
Helpers pour envoyer des messages Telegram avec retry.
Python 3.14 + anyio a un bug TLS intermittent sur les nouvelles connexions.
La solution : réessayer — la connexion du pool est réutilisée dès le 2ème essai.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def send_message(
    chat_id: int | str,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
    bot=None,
) -> bool:
    """
    Envoie un message Telegram avec retry x5.
    Passe le bot via le paramètre ou utilise httpx directement.
    """
    if bot is None:
        # Fallback sans bot : log et retourne False
        logger.warning("send_message appelé sans bot instance")
        return False

    for attempt in range(5):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return True
        except Exception as e:
            if attempt < 4:
                await asyncio.sleep(0.3 * (attempt + 1))
            else:
                logger.warning(f"send_message failed after 5 attempts: {e}")
    return False
