import uuid
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base_mixin import TimestampMixin, UUIDMixin


class PushSubscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "push_subscriptions"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE")
    )
    endpoint:  Mapped[str] = mapped_column(Text, unique=True)
    keys:      Mapped[dict] = mapped_column(JSONB)  # {p256dh, auth}
