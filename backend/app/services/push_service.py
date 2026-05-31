"""
Web Push Notifications (C) — via VAPID / pywebpush.
Envoie des notifications push aux navigateurs qui se sont abonnés.
"""
import asyncio
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def send_push_notification(
    subscription: dict,
    title: str,
    body: str,
    url: str = "",
    icon: str = "/icon-192.png",
) -> bool:
    """
    Envoie une notification push à un abonnement.
    subscription = {endpoint, keys: {p256dh, auth}}
    """
    if not settings.vapid_private_key or not settings.vapid_public_key:
        logger.info("VAPID non configuré — push skipped")
        return False

    payload = json.dumps({
        "title": title,
        "body":  body,
        "icon":  icon,
        "url":   url,
        "badge": "/icon-192.png",
    })

    def _send_sync():
        import base64
        from py_vapid import Vapid
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, NoEncryption, load_pem_private_key
        )
        from pywebpush import webpush, WebPushException

        # Décoder la clé privée PEM depuis base64
        pem_bytes = base64.urlsafe_b64decode(
            settings.vapid_private_key + "=="  # padding
        )

        try:
            webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=pem_bytes.decode(),
                vapid_claims={
                    "sub": settings.vapid_claims_email,
                    "aud": subscription["endpoint"].split("/")[2],
                },
            )
            return True
        except WebPushException as e:
            logger.warning("Push failed: %s", e)
            return False

    try:
        return await asyncio.to_thread(_send_sync)
    except Exception as e:
        logger.warning("Push error: %s", e)
        return False


async def send_push_to_all(
    subscriptions: list[dict],
    title: str,
    body: str,
    url: str = "",
) -> int:
    """Envoie une notification push à tous les abonnements. Retourne le nombre de succès."""
    if not subscriptions:
        return 0
    results = await asyncio.gather(*[
        send_push_notification(sub, title, body, url)
        for sub in subscriptions
    ])
    count = sum(1 for r in results if r)
    logger.info("Push sent: %d/%d", count, len(subscriptions))
    return count
