"""
Tests de vérification des signatures de webhooks (utils/crypto.py).

Sécurité : ces fonctions sont la seule barrière contre des webhooks falsifiés
(Stripe → déclenche une réservation ; Clerk → crée des comptes ; Telegram →
relaye des updates). L'audit a relevé que les routeurs Telegram/Eventbrite
n'appellent PAS ces vérifs — mais les fonctions elles-mêmes doivent être
correctes. On verrouille ici : signature valide → accepté, falsifiée → rejeté.
"""
import base64
import hashlib
import hmac
import json
import time

from app.config import settings
from app.utils.crypto import (
    verify_clerk_webhook,
    verify_stripe_webhook,
    verify_telegram_webhook,
)

# ─── Stripe ──────────────────────────────────────────────────────────────────

STRIPE_SECRET = "whsec_test_stripe_secret_123"


def _stripe_signature(payload: bytes, secret: str, ts: int | None = None) -> str:
    ts = ts or int(time.time())
    signed = f"{ts}.{payload.decode()}".encode()
    v1 = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={v1}"


def test_stripe_valid_signature_returns_event(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", STRIPE_SECRET)
    payload = json.dumps(
        {
            "id": "evt_1",
            "object": "event",  # Stripe exige ce champ top-level
            "type": "payment_intent.succeeded",
            "data": {"object": {}},
        }
    ).encode()
    sig = _stripe_signature(payload, STRIPE_SECRET)
    event = verify_stripe_webhook(payload, sig)
    assert event is not None
    assert event["type"] == "payment_intent.succeeded"


def test_stripe_wrong_secret_rejected(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", STRIPE_SECRET)
    payload = json.dumps({"id": "evt_2", "type": "x"}).encode()
    sig = _stripe_signature(payload, "whsec_attacker_secret")  # mauvaise clé
    assert verify_stripe_webhook(payload, sig) is None


def test_stripe_tampered_payload_rejected(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", STRIPE_SECRET)
    payload = json.dumps({"id": "evt_3", "type": "ok"}).encode()
    sig = _stripe_signature(payload, STRIPE_SECRET)
    tampered = json.dumps({"id": "evt_3", "type": "HACKED"}).encode()
    assert verify_stripe_webhook(tampered, sig) is None


def test_stripe_garbage_signature_rejected(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", STRIPE_SECRET)
    assert verify_stripe_webhook(b"{}", "not-a-real-signature") is None


# ─── Clerk (svix) ────────────────────────────────────────────────────────────

# clé HMAC brute → encodée en base64 → préfixée whsec_ (format attendu par le code)
_CLERK_KEY = b"clerk-test-signing-key"
CLERK_SECRET = "whsec_" + base64.b64encode(_CLERK_KEY).decode()


def _clerk_signature(svix_id: str, ts: str, payload: bytes) -> str:
    msg = f"{svix_id}.{ts}.{payload.decode()}".encode()
    digest = hmac.new(_CLERK_KEY, msg, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def test_clerk_valid_signature_accepted(monkeypatch):
    monkeypatch.setattr(settings, "clerk_webhook_secret", CLERK_SECRET)
    payload = json.dumps({"type": "user.created"}).encode()
    sid, ts = "msg_123", "1700000000"
    sig = _clerk_signature(sid, ts, payload)
    assert verify_clerk_webhook(payload, sid, ts, sig) is True


def test_clerk_multiple_signatures_one_valid(monkeypatch):
    # svix peut envoyer plusieurs signatures séparées par des espaces
    monkeypatch.setattr(settings, "clerk_webhook_secret", CLERK_SECRET)
    payload = json.dumps({"type": "user.created"}).encode()
    sid, ts = "msg_456", "1700000001"
    good = _clerk_signature(sid, ts, payload)
    combined = f"v1,bogussignature {good}"
    assert verify_clerk_webhook(payload, sid, ts, combined) is True


def test_clerk_tampered_payload_rejected(monkeypatch):
    monkeypatch.setattr(settings, "clerk_webhook_secret", CLERK_SECRET)
    payload = json.dumps({"type": "user.created"}).encode()
    sid, ts = "msg_789", "1700000002"
    sig = _clerk_signature(sid, ts, payload)
    tampered = json.dumps({"type": "admin.granted"}).encode()
    assert verify_clerk_webhook(tampered, sid, ts, sig) is False


def test_clerk_wrong_secret_rejected(monkeypatch):
    monkeypatch.setattr(settings, "clerk_webhook_secret", CLERK_SECRET)
    payload = b"{}"
    sid, ts = "msg_x", "1700000003"
    # signature calculée avec une autre clé
    other = hmac.new(b"wrong-key", f"{sid}.{ts}.{{}}".encode(), hashlib.sha256).digest()
    sig = "v1," + base64.b64encode(other).decode()
    assert verify_clerk_webhook(payload, sid, ts, sig) is False


def test_clerk_malformed_signature_returns_false(monkeypatch):
    monkeypatch.setattr(settings, "clerk_webhook_secret", CLERK_SECRET)
    assert verify_clerk_webhook(b"{}", "id", "ts", "garbage") is False


# ─── Telegram ────────────────────────────────────────────────────────────────

TG_TOKEN = "123456:ABC-DEF-token"


def test_telegram_valid_secret_accepted():
    expected = hashlib.sha256(TG_TOKEN.encode()).hexdigest()
    assert verify_telegram_webhook(TG_TOKEN, expected) is True


def test_telegram_wrong_secret_rejected():
    assert verify_telegram_webhook(TG_TOKEN, "deadbeef") is False


def test_telegram_empty_secret_rejected():
    assert verify_telegram_webhook(TG_TOKEN, "") is False
