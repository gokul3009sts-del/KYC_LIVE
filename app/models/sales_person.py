"""
models/sales_person.py

Shared with the admin panel — both apps read the same sales_persons table.
Declared here so the user app's metadata knows about it (needed for
create_all and for migrations).
"""
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime

from app.database import Base


class SalesPerson(Base):
    __tablename__ = "sales_persons"

    id         = Column(String(36),  primary_key=True)
    name       = Column(String(150), nullable=False, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        nullable=False)

    def to_dict(self):
        return {
            "id":         self.id,
            "name":       self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
