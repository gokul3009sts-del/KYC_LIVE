"""
models/log.py — Audit & verification log model.
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class LogEvent(str, enum.Enum):
    REGISTER = "register"
    LOGIN = "login"
    LOGOUT = "logout"
    OTP_SENT = "otp_sent"
    OTP_VERIFIED = "otp_verified"
    OTP_FAILED = "otp_failed"
    OTP_RESENT = "otp_resent"
    OTP_EXPIRED = "otp_expired"
    KYC_SUBMITTED = "kyc_submitted"
    TOKEN_REFRESHED = "token_refreshed"
    ADMIN_ACTION = "admin_action"
    PASSWORD_CHANGED = "password_changed"


class VerificationLog(Base):
    __tablename__ = "verification_logs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # values_callable makes SQLAlchemy persist the enum VALUE ('register')
    # rather than its NAME ('REGISTER'). MySQL matched these case-
    # insensitively so it worked by accident; PostgreSQL does not.
    event = Column(Enum(LogEvent, values_callable=lambda e: [m.value for m in e]),
                   nullable=False, index=True)
    channel = Column(String(10), nullable=True)    # 'email' | 'phone' | None
    ip_address = Column(String(45), nullable=True) # IPv4/IPv6
    user_agent = Column(String(512), nullable=True)
    detail = Column(Text, nullable=True)            # JSON string with extra context
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    user = relationship("User", back_populates="logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event": self.event.value if self.event else None,
            "channel": self.channel,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "detail": self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
