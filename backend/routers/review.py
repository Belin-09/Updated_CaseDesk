from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from database import get_db
from models import Case, CaseFile, AuditLog
from auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/review", tags=["Manual Review"])


# ── Schemas ────────────────────────────────────────────────────────────────

class ResolveRequest(BaseModel):
    analyst: Optional[str] = None
    investigating_officer: Optional[str] = None
    pertains_service_no: Optional[str] = None
    pertains_name: Optional[str] = None
    pertains_unit: Optional[str] = None
    date_deposition: Optional[str] = None
    date_issuance: Optional[str] = None
    date_intimation: Optional[str] = None
    date_return: Optional[str] = None
    incident_type: Optional[str] = None
    command: Optional[str] = None
    review_note: Optional[str] = None


class EscalateRequest(BaseModel):
    review_note: str  # required — must explain why escalating


# ── GET /review — list flagged cases ──────────────────────────────────────

@router.get("/")
def list_flagged_cases(
    error_reason: Optional[str] = Query(None, description="Filter by EMPTY_TEXT, LOW_FIELDS, LOW_OCR_CONFIDENCE, EXTRACTION_EXCEPTION"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(Case).filter(Case.error_flag == True)

    if error_reason:
        query = query.filter(Case.error_reason == error_reason)

    query = query.order_by(Case.created_at.desc())

    total = query.count()
    cases = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "cases": [
            {
                "id": c.id,
                "case_name": c.case_name,
                "file_name": c.file_name,
                "error_reason": c.error_reason,
                "analyst": c.analyst,
                "investigating_officer": c.investigating_officer,
                "pertains_name": c.pertains_name,
                "incident_type": c.incident_type,
                "uploaded_by": c.uploaded_by,
                "created_at": c.created_at,
            }
            for c in cases
        ]
    }


# ── GET /review/{id} — flagged case detail ─────────────────────────────────

@router.get("/{case_id}")
def get_flagged_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if not case.error_flag:
        raise HTTPException(status_code=400, detail="This case is not flagged for review")

    files = db.query(CaseFile).filter(CaseFile.case_id == case_id).all()

    return {
        "id": case.id,
        "case_name": case.case_name,
        "error_reason": case.error_reason,
        "raw_text": case.raw_text,
        "analyst": case.analyst,
        "investigating_officer": case.investigating_officer,
        "pertains_service_no": case.pertains_service_no,
        "pertains_name": case.pertains_name,
        "pertains_unit": case.pertains_unit,
        "date_deposition": case.date_deposition,
        "date_issuance": case.date_issuance,
        "date_intimation": case.date_intimation,
        "date_return": case.date_return,
        "incident_type": case.incident_type,
        "command": case.command,
        "review_note": case.review_note,
        "files": [
            {
                "id": f.id,
                "file_name": f.file_name,
                "file_type": f.file_type,
                "raw_text": f.raw_text,
                "ocr_confidence": f.ocr_confidence,
                "extraction_error": f.extraction_error,
            }
            for f in files
        ]
    }


# ── PUT /review/{id}/resolve ───────────────────────────────────────────────

@router.put("/{case_id}/resolve")
def resolve_case(
    case_id: int,
    payload: ResolveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if not case.error_flag:
        raise HTTPException(status_code=400, detail="This case is not flagged for review")

    update_data = payload.dict(exclude_unset=True, exclude={"review_note"})
    for field, value in update_data.items():
        setattr(case, field, value)

    # Clear the flag — officer has corrected it
    case.error_flag = False
    case.error_reason = None
    case.review_note = payload.review_note
    case.reviewed_by = current_user.username
    case.reviewed_at = datetime.utcnow()
    case.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(case)

    log = AuditLog(
        username=current_user.username,
        action="RESOLVED_REVIEW",
        case_id=case.id,
        details=f"Resolved flagged case, corrected: {', '.join(update_data.keys()) or 'none'}"
    )
    db.add(log)
    db.commit()

    return {"message": "Case resolved successfully", "case_id": case.id}


# ── PUT /review/{id}/escalate ──────────────────────────────────────────────

@router.put("/{case_id}/escalate")
def escalate_case(
    case_id: int,
    payload: EscalateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if not case.error_flag:
        raise HTTPException(status_code=400, detail="This case is not flagged for review")

    # Stays flagged, but now has an escalation note + who escalated it
    case.review_note = payload.review_note
    case.reviewed_by = current_user.username
    case.reviewed_at = datetime.utcnow()
    case.error_reason = "ESCALATED"
    case.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(case)

    log = AuditLog(
        username=current_user.username,
        action="ESCALATED_REVIEW",
        case_id=case.id,
        details=f"Escalated: {payload.review_note}"
    )
    db.add(log)
    db.commit()

    return {"message": "Case escalated successfully", "case_id": case.id}