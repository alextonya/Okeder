from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.utils.crypto import verify_stripe_webhook, verify_telegram_webhook

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    event = verify_stripe_webhook(payload, sig)
    if not event:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    from app.services.stripe_service import handle_stripe_event
    await handle_stripe_event(event, db)
    return {"ok": True}


@router.post("/eventbrite")
async def eventbrite_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    from app.services.eventbrite_service import handle_eventbrite_webhook
    await handle_eventbrite_webhook(body, db)
    return {"ok": True}


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """Passthrough vers le bot — utilisé en mode webhook prod.

    Telegram renvoie le secret configuré via setWebhook(secret_token=...) dans
    l'en-tête X-Telegram-Bot-Api-Secret-Token. Convention du projet : ce secret
    vaut sha256(bot_token) (cf. verify_telegram_webhook).
    """
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not verify_telegram_webhook(settings.telegram_bot_token, secret_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")

    body = await request.json()
    from app.services.telegram_relay import relay_update
    await relay_update(body)
    return {"ok": True}
