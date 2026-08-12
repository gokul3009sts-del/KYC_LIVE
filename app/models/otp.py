"""
models/otp.py — OTP record model. OTP length = 4 digits for this flow.
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class OTPChannel(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"
    BOTH  = "both"   # single OTP dispatched to both channels simultaneously


class OTPStatus(str, enum.Enum):
    PENDING   = "pending"
    VERIFIED  = "verified"
    EXPIRED   = "expired"
    EXHAUSTED = "exhausted"


class OTPRecord(Base):
    __tablename__ = "otp_records"

    id          = Column(String(36), primary_key=True)
    user_id     = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    # channel = 'both' means same OTP was sent to email AND phone simultaneously
    channel     = Column(Enum(OTPChannel, values_callable=lambda e: [m.value for m in e]),
                         nullable=False)
    destination = Column(String(512), nullable=False)   # "email|phone" joined
    otp_hash    = Column(String(255), nullable=False)
    status      = Column(Enum(OTPStatus, values_callable=lambda e: [m.value for m in e]),
                         default=OTPStatus.PENDING, nullable=False)
    attempts       = Column(Integer, default=0,  nullable=False)
    max_attempts   = Column(Integer, default=5,  nullable=False)
    expires_at     = Column(DateTime, nullable=False)
    verified_at    = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    resend_count   = Column(Integer, default=0,  nullable=False)
    last_resent_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="otps")

    @property
    def is_expired(self):
        return datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc)

    @property
    def is_exhausted(self):
        return self.attempts >= self.max_attempts

    def to_dict(self):
        return {
            "id":           self.id,
            "user_id":      self.user_id,
            "channel":      self.channel.value if self.channel else None,
            "destination":  self.destination,
            "status":       self.status.value  if self.status  else None,
            "attempts":     self.attempts,
            "max_attempts": self.max_attempts,
            "expires_at":   self.expires_at.isoformat()    if self.expires_at  else None,
            "verified_at":  self.verified_at.isoformat()   if self.verified_at else None,
            "created_at":   self.created_at.isoformat()    if self.created_at  else None,
            "resend_count": self.resend_count,
        }
