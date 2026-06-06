from sqlalchemy import BigInteger, Boolean, DateTime, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import TimestampMixin, UUIDMixin


class Member(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "members"

    clerk_user_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)  # pour WhatsApp notifications
    whatsapp_notify: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    # Compte PWA : non-null = email vérifié via OTP (= vrai compte Okeder)
    email_verified_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
