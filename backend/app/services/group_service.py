import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.group import GroupMembership
from app.models.member import Member


async def add_member_to_group(
    group_id: uuid.UUID, body: dict, current_member: Member, db: AsyncSession
) -> None:
    telegram_id = body.get("telegram_user_id")
    email = body.get("email")

    if telegram_id:
        result = await db.execute(select(Member).where(Member.telegram_user_id == telegram_id))
    elif email:
        result = await db.execute(select(Member).where(Member.email == email))
    else:
        raise ValueError("telegram_user_id or email required")

    member = result.scalar_one_or_none()
    if not member:
        # Créer un membre fantôme — sera complété à la première interaction
        member = Member(
            telegram_user_id=telegram_id,
            email=email,
            display_name=email or str(telegram_id),
        )
        db.add(member)
        await db.flush()

    exists = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.member_id == member.id,
        )
    )
    if not exists.scalar_one_or_none():
        db.add(GroupMembership(group_id=group_id, member_id=member.id))
        await db.commit()
