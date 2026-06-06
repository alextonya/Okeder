import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.member import Member


async def verify_clerk_token(token: str) -> str | None:
    """Vérifie le JWT Clerk et retourne le clerk_user_id."""
    # Dev bypass : token factice émis par le mock Clerk du PWA (auth désactivée en dev)
    if settings.is_dev and token == "dev-token":
        return "dev_user_okeder"
    try:
        import httpx
        from jose import jwt

        async with httpx.AsyncClient() as client:
            resp = await client.get(settings.clerk_jwks_url)
            jwks = resp.json()

        payload = jwt.decode(token, jwks, algorithms=["RS256"])
        return payload.get("sub")
    except Exception:
        return None


async def handle_clerk_webhook(payload: bytes, db: AsyncSession) -> None:
    """Provisionne un membre depuis le webhook Clerk user.created."""
    data = json.loads(payload)
    if data.get("type") != "user.created":
        return

    user = data["data"]
    clerk_user_id = user["id"]
    email = (user.get("email_addresses") or [{}])[0].get("email_address")
    display_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or email

    result = await db.execute(select(Member).where(Member.clerk_user_id == clerk_user_id))
    if not result.scalar_one_or_none():
        member = Member(clerk_user_id=clerk_user_id, email=email, display_name=display_name or "")
        db.add(member)
        await db.commit()
