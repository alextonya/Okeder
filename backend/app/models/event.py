import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import TimestampMixin, UUIDMixin


class EventStatus:
    COLLECTING = "collecting"
    DECIDING = "deciding"
    PROPOSED = "proposed"
    COMMITTING = "committing"
    BOOKING = "booking"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    EXPIRED = "expired"


class Event(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "events"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE")
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default=EventStatus.COLLECTING)
    constraint_deadline: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    # Wizard of Oz: initiateur gère manuellement jusqu'à désactivation
    wizard_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id"), nullable=True
    )
