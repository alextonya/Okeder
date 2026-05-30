import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.deps import get_current_member
from app.models.group import Group, GroupMembership
from app.models.member import Member

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    group = Group(name=body["name"], initiator_id=current_member.id)
    db.add(group)
    await db.flush()
    membership = GroupMembership(group_id=group.id, member_id=current_member.id, role="initiator")
    db.add(membership)
    await db.commit()
    await db.refresh(group)
    return {"id": str(group.id), "name": group.name}


@router.get("/{group_id}")
async def get_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"id": str(group.id), "name": group.name}


@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    group_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Add a member by telegram_user_id or email."""
    from app.services.group_service import add_member_to_group

    await add_member_to_group(group_id, body, current_member, db)
    return {"ok": True}
