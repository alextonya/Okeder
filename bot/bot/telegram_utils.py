"""
Fonctions Telegram utilisant urllib au lieu de httpx.
Évite le bug TLS anyio/Python 3.14 sur les appels sortants.
"""
import asyncio
import json
import urllib.error
import urllib.request

from bot.config import settings


async def send_message(
    chat_id: int | str,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
) -> bool:
    """Envoie un message Telegram via urllib (pas d'httpx)."""
    payload: dict = {
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    def _send():
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return True
        except urllib.error.HTTPError as e:
            import logging
            logging.getLogger(__name__).warning(
                f"sendMessage {e.code}: {e.read().decode()[:300]}"
            )
            return False
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"sendMessage failed: {e}")
            return False

    return await asyncio.to_thread(_send)
