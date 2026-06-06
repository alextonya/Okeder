from sqlalchemy import Boolean, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base_mixin import TimestampMixin, UUIDMixin


class OtpCode(UUIDMixin, TimestampMixin, Base):
    """Code OTP à usage unique pour la connexion email des comptes PWA."""
    __tablename__ = "otp_codes"

    email: Mapped[str] = mapped_column(Text, index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
