from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
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
    analyst: Optional[str] = None
    investigating_officer: Optional[str] = None
    pertains_service_no: Optional[str] = None
    pertains_name: Optional[str] = None
    pertains_unit: Optional[str] = None
    date_receiving: Optional[str] = None
    date_completion: Optional[str] = None
    date_dispatch: Optional[str] = None
    status: Optional[str] = None


def count_hits(case, search_term: str) -> int:
    if not search_term:
        return 0
    # Normalize search term by replacing spaces and hyphens with a single space
    search_norm = re.sub(r'[\s\-]+', ' ', search_term.lower()).strip()
    
    # Only count hits inside raw_text, notes, and evidence
    fields = [
        case.raw_text,
        case.notes,
        case.evidence
    ]
    count = 0
    for field in fields:
        if field:
            field_norm = re.sub(r'[\s\-]+', ' ', field.lower())
            count += field_norm.count(search_norm)
    return count


# ── GET /cases/years — list all available case years ────────────────────────
@router.get("/years")
def get_case_years(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    all_cases = db.query(Case.source_folder, Case.case_name, Case.date, Case.created_at).all()
    year_counts = defaultdict(int)
    for c in all_cases:
        yr = "Unknown"
        if c.source_folder:
            m = re.search(r"[\/\\](20\d\d|19\d\d)[\/\\]", c.source_folder)
            if m:
                yr = m.group(1)
        if yr == "Unknown" and c.case_name:
            m = re.search(r"\b(20\d\d|19\d\d)\b", c.case_name)
            if m:
                yr = m.group(1)
        if yr == "Unknown" and c.date:
            m = re.search(r"\b(20\d\d|19\d\d)\b", c.date)
            if m:
                yr = m.group(1)
        if yr == "Unknown" and c.created_at:
            yr = str(c.created_at.year)
        
        year_counts[yr] += 1
        
    sorted_years = sorted([{"year": y, "count": count} for y, count in year_counts.items() if y != "Unknown"], key=lambda x: x["year"], reverse=True)
    if "Unknown" in year_counts:
        sorted_years.append({"year": "Unknown", "count": year_counts["Unknown"]})
        
    return sorted_years


# ── GET /cases — list with search, filter, sort ──────────────────────────────

@router.get("/")
def list_cases(
    search: Optional[str] = Query(None, description="Search across officer, location, complainant, case_name"),
    case_search: Optional[str] = Query(None, description="Search strictly by folder name, file name, or ID"),
    status: Optional[str] = Query(None, description="Filter by status: open/closed/pending"),
    incident_type: Optional[str] = Query(None, description="Filter by incident type"),
    error_flag: Optional[bool] = Query(None, description="Filter flagged cases"),
    year: Optional[str] = Query(None, description="Filter cases by year"),
    command: Optional[str] = Query(None, description="Filter cases by military command"),
    sort_by: str = Query("created_at", description="Sort field: created_at, date, officer, status"),
    order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(Case)

    # Search strictly by folder name, file name, or ID
    if case_search:
        cs_term = case_search.strip()
        if re.match(r'^#\d+$', cs_term):
            digits = int(re.sub(r'\D', '', cs_term))
            query = query.filter(Case.id == digits)
        else:
            w = re.sub(r'[\s\-]+', '%', cs_term)
            p_full = '%' + w + '%'
            p_bound1 = '%' + w + '-%'
            p_bound2 = '%' + w + ' %'

            if re.search(r'\d{4}', cs_term):
                pattern_cond = or_(
                    Case.case_name.ilike(p_full), Case.file_name.ilike(p_full)
                )
            else:
                pattern_cond = or_(
                    Case.case_name.ilike(p_bound1), Case.file_name.ilike(p_bound1),
                    Case.case_name.ilike(p_bound2), Case.file_name.ilike(p_bound2),
                    Case.case_name.ilike(f"%{cs_term}"), Case.file_name.ilike(f"%{cs_term}")
                )

            if cs_term.isdigit():
                query = query.filter(or_(Case.id == int(cs_term), pattern_cond))
            else:
                query = query.filter(pattern_cond)

    # Search across multiple fields using token-based AND matching
    if search:
        search_term = search.strip()
        # Check if searching for a case folder name pattern (e.g. "Case No-12" or "Case 12")
        if re.match(r'^case\s*(?:no)?[\s\-]*\d+', search_term.lower()):
            w = re.sub(r'[\s\-]+', '%', search_term)
            p_full = '%' + w + '%'
            p_bound1 = '%' + w + '-%'
            p_bound2 = '%' + w + ' %'

            if re.search(r'\d{4}', search_term):
                query = query.filter(or_(Case.case_name.ilike(p_full), Case.file_name.ilike(p_full)))
            else:
                query = query.filter(or_(
                    Case.case_name.ilike(p_bound1), Case.file_name.ilike(p_bound1),
                    Case.case_name.ilike(p_bound2), Case.file_name.ilike(p_bound2),
                    Case.case_name.ilike(f"%{search_term}"), Case.file_name.ilike(f"%{search_term}")
                ))
        else:
            tokens = [t.strip() for t in re.split(r'[\s\-]+', search_term) if t.strip()]
            if tokens:
                token_conditions = []
                for t in tokens:
                    token_conditions.append(
                        or_(
                            Case.case_name.ilike(f"%{t}%"),
                            Case.file_name.ilike(f"%{t}%"),
                            Case.officer.ilike(f"%{t}%"),
                            Case.location.ilike(f"%{t}%"),
                            Case.complainant.ilike(f"%{t}%"),
                            Case.suspect.ilike(f"%{t}%"),
                            Case.incident_type.ilike(f"%{t}%"),
                            Case.notes.ilike(f"%{t}%"),
                            Case.raw_text.ilike(f"%{t}%"),
                        )
                    )
                query = query.filter(and_(*token_conditions))

    # Filters
    if status:
        query = query.filter(Case.status == status)
    if incident_type:
        query = query.filter(Case.incident_type.ilike(f"%{incident_type}%"))
    if command:
        if command.lower() == "unassigned":
            query = query.filter(or_(Case.command == None, Case.command == ""))
        else:
            query = query.filter(Case.command == command)
    if error_flag is not None:
        query = query.filter(Case.error_flag == error_flag)

    # Sorting
    sort_column = getattr(Case, sort_by, Case.created_at)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    matched_files_map = defaultdict(list)
    if search or year:
        all_cases = query.all()

        # Post-filter by year in memory
        if year:
            filtered = []
            for c in all_cases:
                c_year = "Unknown"
                if c.source_folder:
                    m = re.search(r"[\/\\](20\d\d|19\d\d)[\/\\]", c.source_folder)
                    if m:
                        c_year = m.group(1)
                if c_year == "Unknown" and c.case_name:
                    m = re.search(r"\b(20\d\d|19\d\d)\b", c.case_name)
                    if m:
                        c_year = m.group(1)
                if c_year == "Unknown" and c.date:
                    m = re.search(r"\b(20\d\d|19\d\d)\b", c.date)
                    if m:
                        c_year = m.group(1)
                if c_year == "Unknown" and c.created_at:
                    c_year = str(c.created_at.year)

                if c_year == year:
                    filtered.append(c)
            all_cases = filtered

        total = len(all_cases)

        if search:
            search_cleaned = search.strip()
            for c in all_cases:
                c.hit_count = count_hits(c, search_cleaned)
            total_hits = sum(c.hit_count for c in all_cases)

            # Sort by hit_count descending
            all_cases.sort(key=lambda x: getattr(x, "hit_count", 0), reverse=True)
        else:
            total_hits = 0

        # Paginate in memory
        start_idx = (page - 1) * page_size
        cases = all_cases[start_idx:start_idx + page_size]

        if search and cases:
            search_cleaned = search.strip()
            case_ids = [c.id for c in cases]
            cfiles = db.query(CaseFile).filter(CaseFile.case_id.in_(case_ids)).all()
            for cf in cfiles:
                if cf.raw_text and search_cleaned.lower() in cf.raw_text.lower():
                    f_hits = cf.raw_text.lower().count(search_cleaned.lower())
                    if f_hits > 0:
                        matched_files_map[cf.case_id].append({
                            "file_name": cf.file_name,
                            "hit_count": f_hits
                        })

            # Fallback if no files are in the CaseFile table
            for c in cases:
                if not matched_files_map[c.id] and c.file_name:
                    f_hits = count_hits(c, search_cleaned)
                    if f_hits > 0:
                        matched_files_map[c.id].append({
                            "file_name": c.file_name,
                            "hit_count": f_hits
                        })
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
                "analyst": c.analyst,
                "investigating_officer": c.investigating_officer,
                "pertains_service_no": c.pertains_service_no,
                "pertains_name": c.pertains_name,
                "pertains_unit": c.pertains_unit,
                "date_receiving": c.date_receiving,
                "date_completion": c.date_completion,
                "date_dispatch": c.date_dispatch,
                "status": c.status,
                "error_flag": c.error_flag,
                "error_reason": c.error_reason,
                "uploaded_by": c.uploaded_by,
                "created_at": c.created_at,
                "hit_count": getattr(c, "hit_count", 0) if search else 0,
                "matched_files": matched_files_map.get(c.id, []) if search else []
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
                "file_path": f.file_path,
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
        "analyst": case.analyst,
        "investigating_officer": case.investigating_officer,
        "pertains_service_no": case.pertains_service_no,
        "pertains_name": case.pertains_name,
        "pertains_unit": case.pertains_unit,
        "date_receiving": case.date_receiving,
        "date_completion": case.date_completion,
        "date_dispatch": case.date_dispatch,
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


# ── POST /cases/{case_id}/reprocess ──────────────────────────────────────────

@router.post("/{case_id}/reprocess")
def reprocess_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    files = db.query(CaseFile).filter(CaseFile.case_id == case_id).all()
    if files:
        merged_parts = []
        for f in files:
            if f.raw_text:
                merged_parts.append(f"--- {f.file_name} ---\n{f.raw_text}")
        merged_text = "\n\n".join(merged_parts)
    else:
        merged_text = case.raw_text or ""

    if not merged_text.strip():
        raise HTTPException(status_code=400, detail="No extracted text found in case files to parse")

    # Re-run parser
    from extractor.field_parser import parse_fields
    fields = parse_fields(merged_text)

    # Update metadata fields
    case.pertains_service_no = fields.get("pertains_service_no")
    case.pertains_name = fields.get("pertains_name")
    case.pertains_unit = fields.get("pertains_unit")
    case.command = fields.get("command")
    case.suspected_pio_numbers = fields.get("suspected_pio_numbers")
    case.suspected_pio_count = fields.get("suspected_pio_count", 0)
    case.incident_type = fields.get("incident_type")

    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(case)

    # Audit log
    db.add(AuditLog(
        username=current_user.username,
        action="REPROCESSED_CASE_DETAILS",
        case_id=case_id,
        details="Reprocessed case document extract fields"
    ))
    db.commit()

    return {
        "message": "Fields reprocessed successfully",
        "fields": {
            "pertains_service_no": case.pertains_service_no,
            "pertains_name": case.pertains_name,
            "pertains_unit": case.pertains_unit,
        }
    }


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


import os
import mimetypes

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPLOAD_DIR = os.path.abspath(os.path.join(BASE_DIR, "uploads"))

def get_safe_file_path(raw_file_path: str, source_folder: Optional[str] = None) -> str:
    if not raw_file_path:
        raise HTTPException(status_code=404, detail="File path not recorded")
    
    if not os.path.isabs(raw_file_path):
        resolved_path = os.path.abspath(os.path.join(BASE_DIR, raw_file_path))
    else:
        resolved_path = os.path.abspath(raw_file_path)
        
    real_path = os.path.realpath(resolved_path)
    
    if not os.path.exists(real_path):
        raise HTTPException(status_code=404, detail="File does not exist on disk")
        
    # Allowed roots: BASE_DIR, UPLOAD_DIR, plus source_folder/file parent dir
    allowed_roots = [os.path.realpath(BASE_DIR), os.path.realpath(UPLOAD_DIR)]
    
    if source_folder:
        sf_abs = os.path.realpath(source_folder if os.path.isabs(source_folder) else os.path.join(BASE_DIR, source_folder))
        allowed_roots.append(sf_abs)
        allowed_roots.append(os.path.realpath(os.path.dirname(sf_abs)))

    # Also allow parent directory of the file itself since it's recorded in DB
    allowed_roots.append(os.path.realpath(os.path.dirname(real_path)))

    # Path traversal check using os.path.normcase for Windows drive letter / case matching
    real_norm = os.path.normcase(real_path)
    is_safe = False
    for root in allowed_roots:
        root_norm = os.path.normcase(root)
        if real_norm == root_norm or real_norm.startswith(root_norm + os.sep) or real_norm.startswith(root_norm + "/"):
            is_safe = True
            break

    if not is_safe:
        raise HTTPException(status_code=403, detail="Access denied: file path is outside authorized directories")
        
    return real_path


# ── GET /cases/{id}/download-source — download the main file ────────────────

@router.get("/{case_id}/download-source")
def download_case_source_file(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(verify_token_from_anywhere)
):
    from fastapi.responses import FileResponse
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    safe_path = get_safe_file_path(case.file_path, case.source_folder)
        
    return FileResponse(
        path=safe_path,
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
    from fastapi.responses import FileResponse
    case_file = db.query(CaseFile).filter(CaseFile.id == file_id).first()
    if not case_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    case = db.query(Case).filter(Case.id == case_file.case_id).first()
    source_folder = case.source_folder if case else None
    
    safe_path = get_safe_file_path(case_file.file_path, source_folder)
        
    return FileResponse(
        path=safe_path,
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
    from fastapi.responses import FileResponse
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    safe_path = get_safe_file_path(case.file_path, case.source_folder)
        
    mime_type, _ = mimetypes.guess_type(safe_path)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    return FileResponse(
        path=safe_path,
        media_type=mime_type,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


# ── GET /cases/files/{file_id}/view — view individual files inline ───────────

@router.get("/files/{file_id}/view")
def view_case_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(verify_token_from_anywhere)
):
    from fastapi.responses import FileResponse
    case_file = db.query(CaseFile).filter(CaseFile.id == file_id).first()
    if not case_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    case = db.query(Case).filter(Case.id == case_file.case_id).first()
    source_folder = case.source_folder if case else None
    
    safe_path = get_safe_file_path(case_file.file_path, source_folder)
        
    mime_type, _ = mimetypes.guess_type(safe_path)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    return FileResponse(
        path=safe_path,
        media_type=mime_type,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )