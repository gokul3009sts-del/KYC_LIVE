"""
models/admin_user.py — Admin panel login accounts.

Separate from the "users" table on purpose: "users" holds travel
agencies going through OTP/KYC, which is a completely different account
type from staff who log into the admin panel with a password. Keeping
them apart means an agency can never accidentally get admin rights, and
the admin table can have its own columns without touching agency data.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Boolean

from app.database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id            = Column(String(36),  primary_key=True)
    name          = Column(String(150), nullable=False)
    email         = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)

    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                           nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
