"""
models/kyc_details.py — KYC Details model.

One row per user.

Panel A:
Agency / owner / email / phone

Panel B:
Authorised person / address / IATA / sales person

Panel C:
Business type / PAN / GST / documents

External API:
NBA World Agent ID / API status / API message
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Enum,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.database import Base


class KYCDetails(Base):

    __tablename__ = "kyc_details"

    # ========================================================
    # PRIMARY / USER
    # ========================================================

    id = Column(
        String(36),
        primary_key=True
    )

    user_id = Column(
        String(36),
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
        index=True
    )

    # ========================================================
    # PANEL A
    # ========================================================

    agency_name = Column(
        String(255),
        nullable=False
    )

    owner_first_name = Column(
        String(100),
        nullable=False
    )

    owner_last_name = Column(
        String(100),
        nullable=False
    )

    email = Column(
        String(255),
        nullable=False
    )

    phone = Column(
        String(15),
        nullable=False
    )

    # ========================================================
    # PANEL B
    # ========================================================

    authorised_first_name = Column(
        String(100),
        nullable=False
    )

    authorised_last_name = Column(
        String(100),
        nullable=False
    )

    designation = Column(
        String(100),
        nullable=False
    )

    landline = Column(
        String(20),
        nullable=True
    )

    iata_status = Column(
        Enum(
            "IATA Accredited Agent",
            "Non-IATA Travel Agent",
            name="iata_status_enum"
        ),
        nullable=False
    )

    iata_number = Column(
        String(20),
        nullable=True
    )

    country = Column(
        String(100),
        nullable=False
    )

    state = Column(
        String(100),
        nullable=False
    )

    city = Column(
        String(100),
        nullable=False
    )

    postal_code = Column(
        String(10),
        nullable=False
    )

    office_address = Column(
        Text,
        nullable=False
    )

    sales_person = Column(
        String(150),
        nullable=True
    )

    # ========================================================
    # PANEL C
    # ========================================================

    business_type = Column(
        String(50),
        nullable=False
    )

    # ========================================================
    # PAN / GST
    # ========================================================

    pan_number = Column(
        String(20),
        nullable=True
    )

    gst_number = Column(
        String(20),
        nullable=True
    )

    # ========================================================
    # DOCUMENTS
    # ========================================================

    doc_folder_path = Column(
        String(500),
        nullable=True
    )

    # ========================================================
    # NBA WORLD EXTERNAL API
    # ========================================================

    # Example:
    # NSSTV0100103

    external_agent_id = Column(
        String(50),
        nullable=True,
        unique=True
    )

    # success / failed / pending

    external_api_status = Column(
        String(30),
        nullable=True
    )

    external_api_message = Column(
        Text,
        nullable=True
    )

    # ========================================================
    # META
    # ========================================================

    submitted_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # ========================================================
    # RELATIONSHIP
    # ========================================================

    user = relationship(
        "User",
        back_populates="kyc_details"
    )

    # ========================================================
    # JSON RESPONSE
    # ========================================================

    def to_dict(self) -> dict:

        return {

            "id": self.id,

            "user_id": self.user_id,

            # ------------------------------------------------
            # Panel A
            # ------------------------------------------------

            "agency_name":
                self.agency_name,

            "owner_first_name":
                self.owner_first_name,

            "owner_last_name":
                self.owner_last_name,

            "email":
                self.email,

            "phone":
                self.phone,

            # ------------------------------------------------
            # Panel B
            # ------------------------------------------------

            "authorised_first_name":
                self.authorised_first_name,

            "authorised_last_name":
                self.authorised_last_name,

            "designation":
                self.designation,

            "landline":
                self.landline,

            "iata_status":
                self.iata_status,

            "iata_number":
                self.iata_number,

            "country":
                self.country,

            "state":
                self.state,

            "city":
                self.city,

            "postal_code":
                self.postal_code,

            "office_address":
                self.office_address,

            "sales_person":
                self.sales_person,

            # ------------------------------------------------
            # Panel C
            # ------------------------------------------------

            "business_type":
                self.business_type,

            # ------------------------------------------------
            # PAN / GST
            # ------------------------------------------------

            "pan_number":
                self.pan_number,

            "gst_number":
                self.gst_number,

            # ------------------------------------------------
            # Documents
            # ------------------------------------------------

            "doc_folder_path":
                self.doc_folder_path,

            # ------------------------------------------------
            # NBA World
            # ------------------------------------------------

            "external_agent_id":
                self.external_agent_id,

            "external_api_status":
                self.external_api_status,

            "external_api_message":
                self.external_api_message,

            # ------------------------------------------------
            # Meta
            # ------------------------------------------------

            "submitted_at":
                (
                    self.submitted_at.isoformat()
                    if self.submitted_at
                    else None
                ),

            "updated_at":
                (
                    self.updated_at.isoformat()
                    if self.updated_at
                    else None
                ),
        }

    # ========================================================
    # REPRESENTATION
    # ========================================================

    def __repr__(self):

        return (
            f"<KYCDetails "
            f"user={self.user_id} "
            f"biz={self.business_type} "
            f"agent={self.external_agent_id}>"
        )