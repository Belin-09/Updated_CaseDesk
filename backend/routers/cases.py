from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from database import get_db
from models import Case, CaseFile, AuditLog
from auth import get_current_user
from pydantic import BaseModel
from datetime import datetime
from collections import defaultdict
from sqlalchemy import text
import re
from sqlalchemy import bindparam


router = APIRouter(prefix="/cases", tags=["Cases"])


# ── Schemas ────────────────────────────────────────────────────────────────

class CaseUpdateRequest(BaseModel):
    officer: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None
    incident_type: Optional[str] = None
    complainant: Optional[str] = None
    suspect: Optional[str] = None
    evidence: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


def count_hits(case, search_term: str) -> int:
    if not search_term:
        return 0
    search_lower = search_term.lower()
    # Only count hits inside raw_text, notes, and evidence (main text/contents)
    # to avoid double counting from metadata fields that were extracted from raw_text
    fields = [
        case.raw_text,
        case.notes,
        case.evidence
    ]
    count = 0
    for field in fields:
        if field:
            count += field.lower().count(search_lower)
    return count


# ── GET /cases — list with search, filter, sort ──────────────────────────────

@router.get("/")
def list_cases(
    search: Optional[str] = Query(None, description="Search across officer, location, complainant, case_name"),
    status: Optional[str] = Query(None, description="Filter by status: open/closed/pending"),
    incident_type: Optional[str] = Query(None, description="Filter by incident type"),
    error_flag: Optional[bool] = Query(None, description="Filter flagged cases"),
    sort_by: str = Query("created_at", description="Sort field: created_at, date, officer, status"),
    order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(Case)

    # Search across multiple fields
    if search:
        search_term = search.strip()
        # Strip boolean-mode special characters to avoid unexpected query behavior
        sanitized = re.sub(r'[+\-><()~*"@]', ' ', search_term).strip()
        
        # Build strict BOOLEAN MODE search query by prefixing every word token with '+'
        # and suffixing the final word with '*' to enforce logical AND search.
        tokens = sanitized.split()
        if tokens:
            boolean_search = " ".join([f"+{t}" for t in tokens[:-1]] + [f"+{tokens[-1]}*"])
        else:
            boolean_search = ""

        if boolean_search:
            query = query.filter(
                or_(
                    text("MATCH(officer, location, complainant, suspect, case_name, raw_text) "
                        "AGAINST (:search IN BOOLEAN MODE)"),
                    Case.incident_type.ilike(f"%{search}%"),
                    Case.notes.ilike(f"%{search}%"),
                )
            ).params(search=boolean_search)

    # Filters
    if status:
        query = query.filter(Case.status == status)
    if incident_type:
        query = query.filter(Case.incident_type.ilike(f"%{incident_type}%"))
    if error_flag is not None:
        query = query.filter(Case.error_flag == error_flag)

    # Sorting
    sort_column = getattr(Case, sort_by, Case.created_at)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    if search:
        search_cleaned = search.strip()
        # Load all matches to count hits
        all_cases = query.all()
        total = len(all_cases)
        for c in all_cases:
            c.hit_count = count_hits(c, search_cleaned)
        total_hits = sum(c.hit_count for c in all_cases)
        
        # Paginate in memory
        start_idx = (page - 1) * page_size
        cases = all_cases[start_idx:start_idx + page_size]
    else:
        total = query.count()
        cases = query.offset((page - 1) * page_size).limit(page_size).all()
        total_hits = 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "total_hits": total_hits,
        "cases": [
            {
                "id": c.id,
                "case_name": c.case_name,
                "file_name": c.file_name,
                "officer": c.officer,
                "date": c.date,
                "location": c.location,
                "incident_type": c.incident_type,
                "complainant": c.complainant,
                "suspect": c.suspect,
                "status": c.status,
                "error_flag": c.error_flag,
                "error_reason": c.error_reason,
                "uploaded_by": c.uploaded_by,
                "created_at": c.created_at,
                "hit_count": getattr(c, "hit_count", 0) if search else 0
            }
            for c in cases
        ]
    }

@router.get("/timeline/all")
def get_timeline(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    cases = db.query(Case).order_by(Case.created_at.desc()).all()

    grouped = defaultdict(list)
    for c in cases:
        date_key = c.created_at.strftime("%Y-%m-%d") if c.created_at else "Unknown"
        grouped[date_key].append({
            "id": c.id,
            "case_name": c.case_name,
            "file_name": c.file_name,
            "officer": c.officer,
            "location": c.location,
            "incident_type": c.incident_type,
            "status": c.status,
            "error_flag": c.error_flag,
            "created_at": c.created_at,
        })

    timeline = [
        {"date": date, "cases": items}
        for date, items in sorted(grouped.items(), reverse=True)
    ]

    return {"timeline": timeline, "total": len(cases)}

# ── GET /cases/{id} — single case detail ──────────────────────────────────

@router.get("/{case_id}")
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    files = db.query(CaseFile).filter(CaseFile.case_id == case_id).all()

    if not files and case.file_name:
        import os
        ext = os.path.splitext(case.file_name)[1].lower() if case.file_name else ""
        file_type = "pdf" if ext == ".pdf" else "docx" if ext == ".docx" else "image" if ext in [".jpg", ".jpeg", ".png"] else "unknown"
        
        files_list = [{
            "id": 0,
            "file_name": case.file_name,
            "file_type": file_type,
            "ocr_confidence": case.ocr_confidence,
            "extraction_error": case.error_reason if case.error_flag else None,
            "raw_text": case.raw_text,
        }]
    else:
        files_list = [
            {
                "id": f.id,
                "file_name": f.file_name,
                "file_type": f.file_type,
                "ocr_confidence": f.ocr_confidence,
                "extraction_error": f.extraction_error,
                "raw_text": f.raw_text,
            }
            for f in files
        ]

    return {
        "id": case.id,
        "case_name": case.case_name,
        "file_name": case.file_name,
        "file_path": case.file_path,
        "source_folder": case.source_folder,
        "officer": case.officer,
        "date": case.date,
        "location": case.location,
        "incident_type": case.incident_type,
        "complainant": case.complainant,
        "suspect": case.suspect,
        "evidence": case.evidence,
        "notes": case.notes,
        "raw_text": case.raw_text,
        "status": case.status,
        "error_flag": case.error_flag,
        "error_reason": case.error_reason,
        "review_note": case.review_note,
        "reviewed_by": case.reviewed_by,
        "reviewed_at": case.reviewed_at,
        "uploaded_by": case.uploaded_by,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "files": files_list
    }


# ── PUT /cases/{id} — edit case fields ────────────────────────────────────

@router.put("/{case_id}")
def update_case(
    case_id: int,
    payload: CaseUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    update_data = payload.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    for field, value in update_data.items():
        setattr(case, field, value)

    case.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(case)

    # Audit log
    log = AuditLog(
        username=current_user.username,
        action="UPDATED_CASE",
        case_id=case.id,
        details=f"Updated fields: {', '.join(update_data.keys())}"
    )
    db.add(log)
    db.commit()

    return {"message": "Case updated successfully", "case_id": case.id}


# ── DELETE /cases/{id} ──────────────────────────────────────────────────

@router.delete("/{case_id}")
def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Delete associated files first
    db.query(CaseFile).filter(CaseFile.case_id == case_id).delete()

    db.delete(case)
    db.commit()

    # Audit log
    log = AuditLog(
        username=current_user.username,
        action="DELETED_CASE",
        case_id=case_id,
        details=f"Deleted case: {case.case_name or case.file_name}"
    )
    db.add(log)
    db.commit()

    return {"message": f"Case {case_id} deleted successfully"}


# ── Query/Header Token Verification Helper ───────────────────────────────────

def verify_token_from_anywhere(
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    from jose import jwt, JWTError
    from auth import SECRET_KEY, ALGORITHM
    from models import User
    
    # 1. Try header
    auth_token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        auth_token = auth_header.split(" ")[1]
        
    # 2. Try query parameter
    if not auth_token:
        auth_token = token
        
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authentication token required")
        
    try:
        payload = jwt.decode(auth_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
        
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    return user


# ── GET /cases/{id}/download-source — download the main file ────────────────

@router.get("/{case_id}/download-source")
def download_case_source_file(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(verify_token_from_anywhere)
):
    import os
    from fastapi.responses import FileResponse
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    file_path = case.file_path
    if not file_path:
        raise HTTPException(status_code=404, detail="Source file path not recorded")
        
    if not os.path.isabs(file_path):
        base_dir = os.path.join(os.path.dirname(__file__), "..")
        resolved_path = os.path.abspath(os.path.join(base_dir, file_path))
    else:
        resolved_path = file_path
        
    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail="File does not exist on disk")
        
    return FileResponse(
        path=resolved_path,
        filename=case.file_name or "source_file",
        media_type="application/octet-stream"
    )


# ── GET /cases/files/{file_id}/download — download individual files ─────────

@router.get("/files/{file_id}/download")
def download_case_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(verify_token_from_anywhere)
):
    import os
    from fastapi.responses import FileResponse
    case_file = db.query(CaseFile).filter(CaseFile.id == file_id).first()
    if not case_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = case_file.file_path
    if not file_path:
        raise HTTPException(status_code=404, detail="File path not recorded")
        
    if not os.path.isabs(file_path):
        base_dir = os.path.join(os.path.dirname(__file__), "..")
        resolved_path = os.path.abspath(os.path.join(base_dir, file_path))
    else:
        resolved_path = file_path
        
    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail="File does not exist on disk")
        
    return FileResponse(
        path=resolved_path,
        filename=case_file.file_name or "source_file",
        media_type="application/octet-stream"
    )


# ── GET /cases/{id}/view-source — view the main file inline ──────────────────

@router.get("/{case_id}/view-source")
def view_case_source_file(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(verify_token_from_anywhere)
):
    import os
    import mimetypes
    from fastapi.responses import FileResponse
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    file_path = case.file_path
    if not file_path:
        raise HTTPException(status_code=404, detail="Source file path not recorded")
        
    if not os.path.isabs(file_path):
        base_dir = os.path.join(os.path.dirname(__file__), "..")
        resolved_path = os.path.abspath(os.path.join(base_dir, file_path))
    else:
        resolved_path = file_path
        
    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail="File does not exist on disk")
        
    mime_type, _ = mimetypes.guess_type(resolved_path)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    return FileResponse(
        path=resolved_path,
        media_type=mime_type
    )


# ── GET /cases/files/{file_id}/view — view individual files inline ───────────

@router.get("/files/{file_id}/view")
def view_case_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(verify_token_from_anywhere)
):
    import os
    import mimetypes
    from fastapi.responses import FileResponse
    case_file = db.query(CaseFile).filter(CaseFile.id == file_id).first()
    if not case_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = case_file.file_path
    if not file_path:
        raise HTTPException(status_code=404, detail="File path not recorded")
        
    if not os.path.isabs(file_path):
        base_dir = os.path.join(os.path.dirname(__file__), "..")
        resolved_path = os.path.abspath(os.path.join(base_dir, file_path))
    else:
        resolved_path = file_path
        
    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail="File does not exist on disk")
        
    mime_type, _ = mimetypes.guess_type(resolved_path)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    return FileResponse(
        path=resolved_path,
        media_type=mime_type
    )