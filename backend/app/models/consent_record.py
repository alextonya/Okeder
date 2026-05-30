import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import UUIDMixin


class ConsentRecord(UUIDMixin, Base):
    __tablename__ = "consent_records"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE")
    )
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1=functional, 2=behavioral, 3=full
    source: Mapped[str] = mapped_column(Text, nullable=False)  # 'telegram_bot'|'pwa_onboarding'|'pwa_settings'
    ip_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
