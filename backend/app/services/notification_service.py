"""
Dispatch de notifications vers Telegram ou WhatsApp.
Utilise urllib (stdlib) au lieu de httpx pour éviter le bug TLS anyio/Python 3.14.
"""
import asyncio
import json
import urllib.error
import urllib.request

import httpx

from app.config import settings


async def send_telegram_message(
    chat_id: int | str, text: str, reply_markup: dict | None = None
) -> None:
    """Envoie un message Telegram via urllib (pas d'httpx — évite bug TLS anyio)."""
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
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
                return resp.read()
        except urllib.error.HTTPError as e:
            # 400/403 → log mais pas d'erreur bloquante
            import logging
            logging.getLogger(__name__).warning(
                f"Telegram sendMessage {e.code}: {e.read().decode()[:200]}"
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Telegram sendMessage failed: {e}")

    # Exécuter en thread pour ne pas bloquer l'event loop async
    await asyncio.to_thread(_send)


async def send_whatsapp_template(phone: str, template_name: str, params: list[str]) -> None:
    """Envoie un message template WhatsApp (notification uniquement — ToS compliant)."""
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
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.whatsapp_api_url}/{settings.whatsapp_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json=payload,
        )


async def relay_telegram_update(body: dict) -> None:
    pass  # TODO M1 — intégration bot
