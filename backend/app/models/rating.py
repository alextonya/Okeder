import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import TimestampMixin, UUIDMixin


class Rating(UUIDMixin, TimestampMixin, Base):
    """Note post-event (1–5) laissée par un membre.

    Une seule note par (event, member) : un re-vote met à jour la valeur
    (contrainte unique + upsert côté routeurs). Alimentera le profil
    comportemental à M6.
    """
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("event_id", "member_id"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE")
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
