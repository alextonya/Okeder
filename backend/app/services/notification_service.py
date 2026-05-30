"""
Dispatch de notifications vers Telegram bot ou WhatsApp (templates uniquement).
WhatsApp = canal de notification seulement. Aucune collecte de données comportementales via API.
"""
import httpx

from app.config import settings


async def send_telegram_message(chat_id: int | str, text: str, reply_markup: dict | None = None) -> None:
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json=payload,
        )


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
