"""
Sessions PWA : cookie signé (JWT) portant le member_id du compte connecté.
Pas de Clerk — comptes Okeder natifs (email + OTP).
"""
from datetime import datetime, timedelta, timezone

from fastapi import Request
from jose import JWTError, jwt

from app.config import settings

ALGO = "HS256"
COOKIE_NAME = "okeder_session"


def create_session_token(member_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(member_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.session_ttl_days)).timestamp()),
    }
    return jwt.encode(payload, settings.session_secret, algorithm=ALGO)


def read_session_token(token: str) -> str | None:
    """Retourne le member_id si le token est valide, sinon None."""
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[ALGO])
        return payload.get("sub")
    except JWTError:
        return None


def member_id_from_request(request: Request) -> str | None:
    """Extrait le member_id du cookie de session (None si absent/invalide)."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return read_session_token(token)


def set_session_cookie(response, member_id: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_token(member_id),
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
