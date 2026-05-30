import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import TimestampMixin, UUIDMixin


class Proposal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "proposals"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(SmallInteger, default=1)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    venue_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    venue_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_time: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    price_per_person: Mapped[int | None] = mapped_column(Integer, nullable=True)  # EUR cents
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Legitimacy block (L4)
    pct_budget_satisfied: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    pct_time_satisfied: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    pct_prefs_satisfied: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    hard_constraints_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    compromise_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    compromise_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    legitimacy_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    generated_by: Mapped[str] = mapped_column(Text, default="wizard")  # 'engine' | 'wizard'
    published: Mapped[bool] = mapped_column(Boolean, default=False)
