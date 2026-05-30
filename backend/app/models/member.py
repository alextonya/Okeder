from sqlalchemy import BigInteger, Boolean, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import TimestampMixin, UUIDMixin


class Member(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "members"

    clerk_user_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_notify: Mapped[bool] = mapped_column(Boolean, default=False)
    # 0=none, 1=functional, 2=behavioral, 3=full
    consent_level: Mapped[int] = mapped_column(SmallInteger, default=0)
