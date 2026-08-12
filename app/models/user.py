"""
models/user.py — User model (passwordless OTP registration flow).
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    USER  = "user"
    ADMIN = "admin"


class UserStatus(str, enum.Enum):
    PENDING       = "pending"
    VERIFIED      = "verified"
    KYC_SUBMITTED = "kyc_submitted"
    ACTIVE        = "active"
    SUSPENDED     = "suspended"


class User(Base):
    __tablename__ = "users"

    id                = Column(String(36),  primary_key=True)
    agency_name       = Column(String(255), nullable=False)
    owner_first_name  = Column(String(100), nullable=False)
    owner_last_name   = Column(String(100), nullable=False)
    email             = Column(String(255), unique=True, nullable=False, index=True)
    phone             = Column(String(15),  unique=True, nullable=False, index=True)

    # Nullable — passwordless OTP-only flow
    password_hash     = Column(String(255), nullable=True, default=None)

    email_verified    = Column(Boolean, default=False, nullable=False)
    phone_verified    = Column(Boolean, default=False, nullable=False)
    # True once ANY single OTP is verified
    otp_verified      = Column(Boolean, default=False, nullable=False)

    role   = Column(Enum(UserRole,   values_callable=lambda e: [m.value for m in e]),
                    default=UserRole.USER,      nullable=False)
    status = Column(Enum(UserStatus, values_callable=lambda e: [m.value for m in e]),
                    default=UserStatus.PENDING, nullable=False)

    kyc_data      = Column(Text,     nullable=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    otps        = relationship("OTPRecord",      back_populates="user", cascade="all, delete-orphan")
    logs        = relationship("VerificationLog", back_populates="user", cascade="all, delete-orphan")
    kyc_details = relationship("KYCDetails",      back_populates="user",
                               uselist=False, cascade="all, delete-orphan")

    def to_dict(self, include_sensitive: bool = False) -> dict:
        data = {
            "id":               self.id,
            "agency_name":      self.agency_name,
            "owner_first_name": self.owner_first_name,
            "owner_last_name":  self.owner_last_name,
            "email":            self.email,
            "phone":            self.phone,
            "email_verified":   self.email_verified,
            "phone_verified":   self.phone_verified,
            "otp_verified":     self.otp_verified,
            "role":             self.role.value   if self.role   else None,
            "status":           self.status.value if self.status else None,
            "created_at":       self.created_at.isoformat()    if self.created_at    else None,
            "updated_at":       self.updated_at.isoformat()    if self.updated_at    else None,
            "last_login_at":    self.last_login_at.isoformat() if self.last_login_at else None,
        }
        if include_sensitive:
            data["kyc_data"] = self.kyc_data
        return data

    def __repr__(self):
        return f"<User {self.email} [{self.status}]>"