import hashlib
import hmac

import stripe

from app.config import settings


def verify_stripe_webhook(payload: bytes, signature: str) -> dict | None:
    """Vérifie la signature HMAC du webhook Stripe."""
    try:
        return stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except (stripe.SignatureVerificationError, ValueError):
        return None


def verify_clerk_webhook(payload: bytes, svix_id: str, svix_ts: str, svix_sig: str) -> bool:
    """Vérifie la signature svix du webhook Clerk."""
    try:
        msg = f"{svix_id}.{svix_ts}.{payload.decode()}"
        secret = settings.clerk_webhook_secret.removeprefix("whsec_")
        import base64
        key = base64.b64decode(secret)
        expected = hmac.new(key, msg.encode(), hashlib.sha256).digest()
        expected_b64 = base64.b64encode(expected).decode()
        for sig in svix_sig.split(" "):
            if sig.startswith("v1,") and hmac.compare_digest(sig[3:], expected_b64):
                return True
        return False
    except Exception:
        return False


def verify_telegram_webhook(token: str, secret_header: str) -> bool:
    """Vérifie le secret token du webhook Telegram."""
    expected = hashlib.sha256(token.encode()).hexdigest()
    return hmac.compare_digest(expected, secret_header)
