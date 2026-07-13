from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base
from sqlalchemy import Float
from sqlalchemy.dialects.mysql import LONGTEXT

class Case(Base):
    __tablename__ = "cases"

    id             = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_name      = Column(Text)
    file_path      = Column(String(500))

    # Extracted fields
    incident_type = Column(String(255), index=True, nullable=True)
    raw_text = Column(LONGTEXT, nullable=True)

    # Status
    status         = Column(String(50), index=True, default="open")

    # Error / Review
    error_flag     = Column(Boolean, default=False)
    error_reason   = Column(String(100), nullable=True)
    review_note    = Column(Text, nullable=True)
    reviewed_by    = Column(String(255), nullable=True)
    reviewed_at    = Column(DateTime, nullable=True)

    # Timestamp
    created_at     = Column(DateTime, server_default=func.now())
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )
    uploaded_by = Column(String(100), nullable=True)

    ocr_confidence = Column(Float, nullable=True)
    case_name     = Column(String(255), nullable=True, index=True)
    source_folder = Column(String(500), nullable=True, index=True)

    file_count    = Column(Integer, nullable=True)
    last_modified = Column(DateTime, nullable=True)

    # Custom Analytics fields
    command       = Column(String(100), nullable=True, index=True)
    suspected_pio_numbers = Column(Text, nullable=True)
    suspected_pio_count   = Column(Integer, default=0)
    has_confirmed_pio     = Column(Boolean, default=False, index=True)
    confirmed_pio_matches = Column(Text, nullable=True)

    # New custom metadata fields
    analyst = Column(String(255), nullable=True)
    investigating_officer = Column(String(255), nullable=True)
    pertains_service_no = Column(String(255), nullable=True, index=True)
    pertains_name = Column(String(255), nullable=True, index=True)
    pertains_unit = Column(String(255), nullable=True, index=True)
    date_deposition = Column(String(100), nullable=True)
    date_issuance = Column(String(100), nullable=True)
    date_intimation = Column(String(100), nullable=True)
    date_return = Column(String(100), nullable=True)

    # Pre-computed year for fast SQL filtering
    year = Column(String(10), nullable=True, index=True)


class ConfirmedPIO(Base):
    __tablename__ = "confirmed_pios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone_number = Column(String(50), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class CaseFile(Base):
    __tablename__ = "case_files"

    id               = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id          = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    file_name        = Column(String(255))
    file_path        = Column(String(500))
    file_type        = Column(String(50))
    raw_text         = Column(LONGTEXT, nullable=True)
    ocr_confidence   = Column(Float, nullable=True)
    extraction_error = Column(String(255), nullable=True)
    created_at       = Column(DateTime, server_default=func.now())
    

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    username = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )

    hashed_password = Column(
        String(255),
        nullable=False
    )

    role = Column(
        String(50),
        default="officer"
    )

    must_change_password = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )



class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    username = Column(String(100))
    action = Column(String(100))

    case_id = Column(
        Integer,
        nullable=True
    )

    details = Column(
        String(500),
        nullable=True
    )

    timestamp = Column(
        DateTime,
        server_default=func.now()
    )    