import uuid

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import UUIDMixin


class BehavioralProfile(UUIDMixin, Base):
    __tablename__ = "behavioral_profiles"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id"), unique=True
    )
    budget_median: Mapped[int | None] = mapped_column(Integer, nullable=True)  # EUR cents
    preferred_categories: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    preferred_days: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    hard_nos: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_commitment_level: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    # pgvector — activé à M6, nullable en attendant
    # embedding: vector(1536) — ajouté via migration Alembic après activation pgvector
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
