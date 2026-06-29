from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from database import Base
from sqlalchemy import Float

class Case(Base):
    __tablename__ = "cases"

    id             = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_name      = Column(String(255))
    file_path      = Column(String(500))

    # Extracted fields
    officer = Column(String(255), index=True, nullable=True)
    date = Column(String(100), nullable=True)
    location = Column(String(255), index=True, nullable=True)
    incident_type = Column(String(255), index=True, nullable=True)
    complainant = Column(String(255), nullable=True)
    suspect = Column(String(255), nullable=True)

    evidence = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)

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

    ocr_confidence = Column(String(20), nullable=True)
    case_name     = Column(String(255), nullable=True, index=True)
    source_folder = Column(String(500), nullable=True, index=True)

    file_count    = Column(Integer, nullable=True)
    last_modified = Column(DateTime, nullable=True)


class CaseFile(Base):
    __tablename__ = "case_files"

    id               = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id          = Column(Integer, index=True, nullable=False)
    file_name        = Column(String(255))
    file_path        = Column(String(500))
    file_type        = Column(String(50))
    raw_text         = Column(Text, nullable=True)
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