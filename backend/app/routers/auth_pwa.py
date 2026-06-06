"""
Auth comptes PWA — email + OTP, session cookie signée.
Endpoints:
  POST /pwa/auth/request-otp  {email}                  -> envoie un code
  POST /pwa/auth/verify-otp   {email, code, name?}      -> ouvre la session
  POST /pwa/auth/logout
  GET  /pwa/auth/me
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.models.member import Member
from app.models.otp_code import OtpCode
from app.services.email_service import send_otp_email
from app.services.session import (
    clear_session_cookie,
    member_id_from_request,
    set_session_cookie,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def _hash_code(email: str, code: str) -> str:
    return hashlib.sha256(f"{email.lower()}:{code}:{settings.session_secret}".encode()).hexdigest()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


@router.post("/pwa/auth/request-otp")
async def request_otp(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    email = _normalize_email(body.get("email", ""))
    if "@" not in email or "." not in email.split("@")[-1]:
        return JSONResponse({"ok": False, "error": "invalid email"}, status_code=400)

    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(timezone.utc)

    db.add(OtpCode(
        email=email,
        code_hash=_hash_code(email, code),
        expires_at=now + timedelta(minutes=settings.otp_ttl_minutes),
    ))
    await db.commit()

    # Le compte existe-t-il déjà ? (pour ne pas redemander le nom)
    acct = await db.execute(
        select(Member).where(Member.email == email, Member.email_verified_at != None)  # noqa: E711
    )
    existing = acct.scalar_one_or_none()
    known = existing is not None

    sent = await send_otp_email(email, code)

    # En dev sans SMTP, on renvoie le code pour pouvoir tester.
    resp = {"ok": True, "sent": sent, "known": known}
    if existing:
        resp["display_name"] = existing.display_name
    if not sent and settings.is_dev:
        resp["dev_code"] = code
    return JSONResponse(resp)


@router.post("/pwa/auth/verify-otp")
async def verify_otp(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    email = _normalize_email(body.get("email", ""))
    code = (body.get("code") or "").strip()
    name = (body.get("name") or "").strip()

    if not email or not code:
        return JSONResponse({"ok": False, "error": "missing fields"}, status_code=400)

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(OtpCode)
        .where(OtpCode.email == email, OtpCode.consumed == False)  # noqa: E712
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()

    if not otp:
        return JSONResponse({"ok": False, "error": "no code requested"}, status_code=400)

    # expires_at peut être renvoyé naïf selon le driver — forcer tz-aware
    exp = otp.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        return JSONResponse({"ok": False, "error": "code expired"}, status_code=400)
    if otp.attempts >= settings.otp_max_attempts:
        return JSONResponse({"ok": False, "error": "too many attempts"}, status_code=429)

    if otp.code_hash != _hash_code(email, code):
        otp.attempts += 1
        await db.commit()
        return JSONResponse({"ok": False, "error": "wrong code"}, status_code=400)

    otp.consumed = True

    # Trouver/créer le compte (email vérifié)
    acct_result = await db.execute(
        select(Member).where(Member.email == email, Member.email_verified_at != None)  # noqa: E711
    )
    member = acct_result.scalar_one_or_none()
    is_new = member is None
    if not member:
        member = Member(
            display_name=name or email.split("@")[0],
            email=email,
            email_verified_at=now,
            consent_level=1,
        )
        db.add(member)
        await db.flush()
    else:
        if name:
            member.display_name = name

    await db.commit()

    needs_name = is_new and not name
    payload = {
        "ok": True,
        "member_id": str(member.id),
        "display_name": member.display_name,
        "needs_name": needs_name,
    }
    response = JSONResponse(payload)
    set_session_cookie(response, str(member.id))
    return response


@router.post("/pwa/auth/logout")
async def logout():
    response = JSONResponse({"ok": True})
    clear_session_cookie(response)
    return response


@router.get("/pwa/auth/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    member_id = member_id_from_request(request)
    if not member_id:
        return JSONResponse({"authenticated": False})
    import uuid
    try:
        result = await db.execute(select(Member).where(Member.id == uuid.UUID(member_id)))
        member = result.scalar_one_or_none()
    except ValueError:
        member = None
    if not member:
        return JSONResponse({"authenticated": False})
    return JSONResponse({
        "authenticated": True,
        "member_id": str(member.id),
        "display_name": member.display_name,
        "email": member.email,
    })
