"""
Helpers Telegram avec retry x5.
Python 3.14 + anyio : bug TLS sur les nouvelles connexions.
Le retry fonctionne car la connexion établie est réutilisée dès le 2ème essai.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def _retry(coro_factory, label: str = "", retries: int = 5) -> bool:
    """Exécute une coroutine avec retry. coro_factory = lambda sans arg."""
    for attempt in range(retries):
        try:
            await coro_factory()
            return True
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(0.3 * (attempt + 1))
            else:
                logger.warning(f"[telegram] {label} failed after {retries} attempts: {e}")
    return False


async def send_message(
    chat_id: int | str,
    text: str,
    parse_mode: str = "HTML",
    reply_markup=None,
    bot=None,
) -> bool:
    if bot is None:
        logger.warning("send_message: bot instance required")
        return False
    return await _retry(
        lambda: bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        ),
        label=f"send_message to {chat_id}",
    )


async def reply_text(
    message,
    text: str,
    parse_mode: str = "HTML",
    reply_markup=None,
) -> bool:
    """Wrapper reply_text avec retry."""
    return await _retry(
        lambda: message.reply_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        ),
        label="reply_text",
    )


async def edit_message_text(
    query,
    text: str,
    parse_mode: str = "HTML",
    reply_markup=None,
) -> bool:
    """Wrapper edit_message_text avec retry."""
    kwargs = {"text": text, "parse_mode": parse_mode}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    return await _retry(
        lambda: query.edit_message_text(**kwargs),
        label="edit_message_text",
    )


async def answer_callback(query, text: str = "", show_alert: bool = False) -> bool:
    """Wrapper answer_callback_query avec retry."""
    return await _retry(
        lambda: query.answer(text=text, show_alert=show_alert),
        label="answer_callback",
    )
