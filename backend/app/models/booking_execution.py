import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import UUIDMixin


class BookingMethod:
    EVENTBRITE_API = "eventbrite_api"
    PREFILLED_FORM = "prefilled_form"
    AI_BROWSER_AGENT = "ai_browser_agent"  # fallback disclosé uniquement


class BookingStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class BookingExecution(UUIDMixin, Base):
    __tablename__ = "booking_executions"

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id")
    )
    method: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default=BookingStatus.PENDING)
    external_booking_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True quand l'agent IA est utilisé — obligatoire per design pour conformité légale
    agent_disclosed: Mapped[bool] = mapped_column(Boolean, default=False)
    attempted_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
