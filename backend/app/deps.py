from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db  # noqa: F401 — re-exported for convenience
from app.models.member import Member

security = HTTPBearer()


async def get_current_member(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> Member:
    """Validate Clerk JWT and return the associated Member row."""
    from app.services.auth_service import verify_clerk_token

    clerk_user_id = await verify_clerk_token(credentials.credentials)
    if not clerk_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    from sqlalchemy import select

    result = await db.execute(select(Member).where(Member.clerk_user_id == clerk_user_id))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member
