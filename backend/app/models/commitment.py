import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import UUIDMixin


class CommitmentLevel:
    SOFT = "soft"
    CONFIRMED = "confirmed"
    HARD = "hard"


class Commitment(UUIDMixin, Base):
    __tablename__ = "commitments"
    __table_args__ = (UniqueConstraint("proposal_id", "member_id"),)

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id", ondelete="CASCADE")
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE")
    )
    level: Mapped[str] = mapped_column(Text, default=CommitmentLevel.SOFT)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paid_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
