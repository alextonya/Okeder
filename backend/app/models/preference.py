import uuid

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import UUIDMixin


class Preference(UUIDMixin, Base):
    __tablename__ = "preferences"
    __table_args__ = (UniqueConstraint("event_id", "member_id"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE")
    )
    budget_min: Mapped[int | None] = mapped_column(Integer, nullable=True)   # EUR cents
    budget_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_slots: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # [{date,start,end}]
    category_prefs: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    hard_constraints: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    soft_preferences: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    raw_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    submitted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    declined: Mapped[bool] = mapped_column(default=False)
