"""
Dispatch de notifications Telegram via urllib avec retry x5.
WinError 10054 / TLS anyio : retry résout le problème car la connexion
établie au démarrage est réutilisée dès le 2ème essai.
"""
import asyncio
import json
import logging
import urllib.error
import urllib.request

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def send_telegram_message(
    chat_id: int | str,
    text: str,
    reply_markup: dict | None = None,
) -> None:
    """Envoie un message Telegram via urllib avec retry x5."""
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    def _attempt():
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read()

    for attempt in range(5):
        try:
            await asyncio.to_thread(_attempt)
            return  # succès
        except urllib.error.HTTPError as e:
            logger.warning(f"Telegram sendMessage HTTP {e.code}: {e.read().decode()[:200]}")
            return  # erreur HTTP → pas la peine de retry
        except Exception as e:
            if attempt < 4:
                await asyncio.sleep(0.3 * (attempt + 1))
            else:
                logger.warning(f"Telegram sendMessage failed after 5 attempts: {e}")


async def send_whatsapp_template(phone: str, template_name: str, params: list[str]) -> None:
    """Envoie un message template WhatsApp (notification uniquement)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [
                {"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}
            ],
        },
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.whatsapp_api_url}/{settings.whatsapp_phone_number_id}/messages",
                headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
                json=payload,
            )
    except Exception as e:
        logger.warning(f"WhatsApp send failed: {e}")


async def relay_telegram_update(body: dict) -> None:
    pass
