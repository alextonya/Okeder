import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
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
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    wizard_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    # Nombre de participants attendus (déclaré par l'organisateur)
    # 0 = non déclaré → fallback sur membres en DB
    expected_participants: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id"), nullable=True
    )
