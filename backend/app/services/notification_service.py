"""
Dispatch de notifications vers Telegram bot ou WhatsApp (templates uniquement).
WhatsApp = canal de notification seulement. Aucune collecte de données comportementales via API.
"""
import httpx

from app.config import settings


async def send_telegram_message(chat_id: int | str, text: str, reply_markup: dict | None = None) -> None:
    import asyncio
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    # Retry x3 — TLS intermittent sur Python 3.14 + anyio
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json=payload,
                )
            return
        except Exception:
            if attempt < 2:
                await asyncio.sleep(0.5)
            # Dernier essai échoué → silencieux (le DM est best-effort)


async def send_whatsapp_template(phone: str, template_name: str, params: list[str]) -> None:
    """Envoie un message template WhatsApp (notification uniquement — ToS compliant)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}],
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
