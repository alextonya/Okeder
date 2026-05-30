from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_member
from app.models.member import Member

router = APIRouter()


@router.post("/clerk-webhook")
async def clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Clerk user.created webhook — provision member row."""
    from app.services.auth_service import handle_clerk_webhook
    from app.utils.crypto import verify_clerk_webhook

    payload = await request.body()
    svix_id = request.headers.get("svix-id", "")
    svix_ts = request.headers.get("svix-timestamp", "")
    svix_sig = request.headers.get("svix-signature", "")

    if not verify_clerk_webhook(payload, svix_id, svix_ts, svix_sig):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    await handle_clerk_webhook(payload, db)
    return {"ok": True}


@router.post("/consent", status_code=201)
async def submit_consent(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Enregistre le consentement RGPD + met à jour le display_name."""
    from datetime import datetime, timezone
    import hashlib

    from app.models.consent_record import ConsentRecord

    if body.get("display_name"):
        current_member.display_name = body["display_name"]

    source = body.get("source", "pwa_onboarding")
    ip_raw = request.client.host if request.client else ""
    ip_hash = hashlib.sha256(ip_raw.encode()).hexdigest()[:16]

    max_level = 0
    for consent in body.get("consents", []):
        level = int(consent["level"])
        record = ConsentRecord(
            member_id=current_member.id,
            level=level,
            source=source,
            ip_hash=ip_hash,
            user_agent=request.headers.get("user-agent", "")[:200],
            granted_at=datetime.now(timezone.utc),
        )
        db.add(record)
        max_level = max(max_level, level)

    current_member.consent_level = max_level
    await db.commit()
    return {"ok": True, "consent_level": max_level}


@router.get("/me")
async def get_me(current_member: Member = Depends(get_current_member)):
    return {
        "id": str(current_member.id),
        "display_name": current_member.display_name,
        "consent_level": current_member.consent_level,
        "telegram_linked": current_member.telegram_user_id is not None,
    }
