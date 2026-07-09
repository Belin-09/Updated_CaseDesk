from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, extract
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

    date_deposition: Optional[str] = None
    date_issuance: Optional[str] = None
    date_intimation: Optional[str] = None
    date_return: Optional[str] = None
    status: Optional[str] = None


def count_hits(case, search_term: str) -> int:
    if not search_term:
        return 0
    # Normalize search term by replacing spaces and hyphens with a single space
    search_norm = re.sub(r'[\s\-]+', ' ', search_term.lower()).strip()
    
    # Only count hits inside raw_text
    fields = [
        case.raw_text
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
    all_cases = db.query(Case.source_folder, Case.case_name, Case.date_deposition, Case.created_at).all()
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
        if yr == "Unknown" and c.date_deposition:
            m = re.search(r"\b(20\d\d|19\d\d)\b", c.date_deposition)
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
                            Case.analyst.ilike(f"%{t}%"),
                            Case.investigating_officer.ilike(f"%{t}%"),
                            Case.pertains_service_no.ilike(f"%{t}%"),
                            Case.pertains_name.ilike(f"%{t}%"),
                            Case.pertains_unit.ilike(f"%{t}%"),
                            Case.incident_type.ilike(f"%{t}%"),
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
                if c_year == "Unknown" and c.date_deposition:
                    m = re.search(r"\b(20\d\d|19\d\d)\b", c.date_deposition)
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
                "incident_type": c.incident_type,
                "analyst": c.analyst,
                "investigating_officer": c.investigating_officer,
                "pertains_service_no": c.pertains_service_no,
                "pertains_name": c.pertains_name,
                "pertains_unit": c.pertains_unit,

                "date_deposition": c.date_deposition,
                "date_issuance": c.date_issuance,
                "date_intimation": c.date_intimation,
                "date_return": c.date_return,
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


@router.get("/search/options")
def get_search_options(db: Session = Depends(get_db)):
    incident_types = [r[0] for r in db.query(Case.incident_type).distinct().filter(Case.incident_type != None).all() if r[0].strip()]
    commands = [r[0] for r in db.query(Case.command).distinct().filter(Case.command != None).all() if r[0].strip()]
    analysts = [r[0] for r in db.query(Case.analyst).distinct().filter(Case.analyst != None).all() if r[0].strip()]
    investigating_officers = [r[0] for r in db.query(Case.investigating_officer).distinct().filter(Case.investigating_officer != None).all() if r[0].strip()]
    
    # Extract unique dates from the 4 date fields
    d1 = [r[0] for r in db.query(Case.date_deposition).distinct().filter(Case.date_deposition != None).all() if r[0].strip() and r[0].strip().lower() != "unknown"]
    d2 = [r[0] for r in db.query(Case.date_issuance).distinct().filter(Case.date_issuance != None).all() if r[0].strip() and r[0].strip().lower() != "unknown"]
    d3 = [r[0] for r in db.query(Case.date_intimation).distinct().filter(Case.date_intimation != None).all() if r[0].strip() and r[0].strip().lower() != "unknown"]
    d4 = [r[0] for r in db.query(Case.date_return).distinct().filter(Case.date_return != None).all() if r[0].strip() and r[0].strip().lower() != "unknown"]
    all_dates = sorted(list(set(d1 + d2 + d3 + d4)))
    
    # Use the same logic as the cases page to extract years
    years_data = get_case_years(db, None)
    years = sorted([y["year"] for y in years_data if y["year"] != "Unknown"], reverse=True)
    
    return {
        "incident_type": sorted(incident_types),
        "command": sorted(commands),
        "analyst": sorted(analysts),
        "investigating_officer": sorted(investigating_officers),
        "dates": all_dates,
        "years": years
    }

import json

@router.get("/search/advanced")
def advanced_search(
    filters: Optional[str] = Query(None, description="JSON array of filters"),
    year: Optional[str] = Query(None, description="Year filter"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(Case)

    global_term = None
    if filters:
        try:
            filter_list = json.loads(filters)
            for f in filter_list:
                category = f.get("category")
                term = f.get("term")
                if not category or not term:
                    continue
                
                term = str(term).strip()
                pattern = f"%{term}%"

                if category in ("random", "case_name"):
                    global_term = term

                if category == "case_name":
                    query = query.filter(Case.case_name.ilike(pattern))
                elif category == "incident_type":
                    query = query.filter(Case.incident_type.ilike(pattern))
                elif category == "command":
                    query = query.filter(Case.command.ilike(pattern))
                elif category == "analyst":
                    query = query.filter(Case.analyst.ilike(pattern))
                elif category == "investigating_officer":
                    query = query.filter(Case.investigating_officer.ilike(pattern))
                elif category == "pertains":
                    query = query.filter(
                        or_(
                            Case.pertains_service_no.ilike(pattern),
                            Case.pertains_name.ilike(pattern),
                            Case.pertains_unit.ilike(pattern)
                        )
                    )
                elif category == "dates":
                    query = query.filter(
                        or_(
                            Case.date_deposition.ilike(pattern),
                            Case.date_issuance.ilike(pattern),
                            Case.date_intimation.ilike(pattern),
                            Case.date_return.ilike(pattern)
                        )
                    )
                elif category == "random":
                    query = query.filter(Case.raw_text.ilike(pattern))
        except Exception:
            pass

    cases = query.all()
    
    filtered_cases = []
    for c in cases:
        if year and year != "all":
            c_year = "Unknown"
            if c.source_folder:
                m = re.search(r"[\/\\](20\d\d|19\d\d)[\/\\]", c.source_folder)
                if m:
                    c_year = m.group(1)
            if c_year == "Unknown" and c.case_name:
                m = re.search(r"\b(20\d\d|19\d\d)\b", c.case_name)
                if m:
                    c_year = m.group(1)
            if c_year == "Unknown" and c.created_at:
                c_year = str(c.created_at.year)
                
            if c_year != year:
                continue
        filtered_cases.append(c)

    matched_files_map = defaultdict(list)
    if global_term and filtered_cases:
        for c in filtered_cases:
            c.hit_count = count_hits(c, global_term)

        case_ids = [c.id for c in filtered_cases]
        cfiles = db.query(CaseFile).filter(CaseFile.case_id.in_(case_ids)).all()
        for cf in cfiles:
            if cf.raw_text and global_term.lower() in cf.raw_text.lower():
                f_hits = cf.raw_text.lower().count(global_term.lower())
                if f_hits > 0:
                    matched_files_map[cf.case_id].append({
                        "file_name": cf.file_name,
                        "hit_count": f_hits
                    })
                    
        for c in filtered_cases:
            if not matched_files_map[c.id] and c.file_name:
                if c.raw_text and global_term.lower() in c.raw_text.lower():
                    matched_files_map[c.id].append({
                        "file_name": c.file_name,
                        "hit_count": getattr(c, "hit_count", 1)
                    })
                    
        filtered_cases.sort(key=lambda x: getattr(x, "hit_count", 0), reverse=True)

    results = []
    for c in filtered_cases:
        results.append({
            "id": c.id,
            "case_name": c.case_name,
            "file_name": c.file_name,
            "incident_type": c.incident_type,
            "status": c.status,
            "analyst": c.analyst,
            "investigating_officer": c.investigating_officer,
            "pertains_name": c.pertains_name,
            "command": c.command,
            "created_at": c.created_at,
            "error_flag": c.error_flag,
            "uploaded_by": c.uploaded_by,
            "hit_count": getattr(c, "hit_count", 0),
            "matched_files": matched_files_map.get(c.id, [])
        })
    return results


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
        "incident_type": case.incident_type,
        "analyst": case.analyst,
        "investigating_officer": case.investigating_officer,
        "pertains_service_no": case.pertains_service_no,
        "pertains_name": case.pertains_name,
        "pertains_unit": case.pertains_unit,

        "date_deposition": case.date_deposition,
        "date_issuance": case.date_issuance,
        "date_intimation": case.date_intimation,
        "date_return": case.date_return,
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
    case.analyst = fields.get("analyst")
    case.investigating_officer = fields.get("investigating_officer")
    case.date_deposition = fields.get("date_deposition")
    case.date_issuance = fields.get("date_issuance")
    case.date_intimation = fields.get("date_intimation")
    case.date_return = fields.get("date_return")
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
            "analyst": case.analyst,
            "investigating_officer": case.investigating_officer,
            "date_deposition": case.date_deposition,
            "date_issuance": case.date_issuance,
            "date_intimation": case.date_intimation,
            "date_return": case.date_return,
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


def convert_docx_to_html(file_path: str, search_term: str = None) -> str:
    from docx import Document
    import html
    try:
        doc = Document(file_path)
        html_parts = []
        html_parts.append("""
        <html>
        <head>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #0f1419;
                color: #e8eaed;
                padding: 20px;
                line-height: 1.6;
            }
            p { margin-bottom: 12px; }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
                background: #1a2129;
                border: 1px solid #2a3441;
            }
            td, th {
                border: 1px solid #2a3441;
                padding: 10px;
                text-align: left;
            }
            th {
                background: #2a3441;
                color: #4f9cff;
                font-weight: 600;
            }
            mark.search-highlight {
                background: rgba(14, 165, 233, 0.25) !important;
                color: #38bdf8 !important;
                padding: 1px 3px;
                border-radius: 3px;
                font-weight: 600;
                transition: background 0.2s, box-shadow 0.2s;
            }
            mark.search-highlight.active-hit {
                background: rgba(250, 204, 21, 0.45) !important;
                color: #fbbf24 !important;
                box-shadow: 0 0 8px rgba(250, 204, 21, 0.5), 0 0 2px rgba(250, 204, 21, 0.3);
                outline: 2px solid rgba(250, 204, 21, 0.6);
                outline-offset: 1px;
            }
        </style>
        </head>
        <body>
        """)
        
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        
        body_elements = doc.element.body
        for child in body_elements:
            tag = child.tag.split('}')[-1]
            if tag == 'p':
                p = Paragraph(child, doc)
                if p.text.strip():
                    html_parts.append(f"<p>{html.escape(p.text)}</p>")
            elif tag == 'tbl':
                t = Table(child, doc)
                html_parts.append("<table>")
                for row in t.rows:
                    html_parts.append("<tr>")
                    for cell in row.cells:
                        cell_text = "<br>".join(html.escape(para.text) for para in cell.paragraphs if para.text.strip())
                        html_parts.append(f"<td>{cell_text}</td>")
                    html_parts.append("</tr>")
                html_parts.append("</table>")
                
        html_parts.append("""
        <script>
            window.addEventListener('message', function(event) {
                if (event.data && event.data.type === 'NAVIGATE_HIT') {
                    const index = event.data.index;
                    const marks = document.querySelectorAll('mark.search-highlight');
                    marks.forEach(m => m.classList.remove('active-hit'));
                    const target = document.getElementById('hit-' + index);
                    if (target) {
                        target.classList.add('active-hit');
                        const targetTop = target.getBoundingClientRect().top + window.scrollY;
                        window.scrollTo({
                            top: targetTop - window.innerHeight / 2,
                            behavior: 'smooth'
                        });
                    }
                }
            });
        </script>
        </body></html>
        """)
        raw_html = "\n".join(html_parts)
        
        if search_term:
            escaped_term = html.escape(search_term)
            pattern = re.compile(r'(<[^>]+>)|(' + re.escape(escaped_term) + r')', re.IGNORECASE)
            hit_index = 0
            def replace_match(m):
                nonlocal hit_index
                if m.group(1):
                    return m.group(1)
                res = f'<mark class="search-highlight" data-hit-index="{hit_index}" id="hit-{hit_index}">{m.group(2)}</mark>'
                hit_index += 1
                return res
            raw_html = pattern.sub(replace_match, raw_html)
            
        return raw_html
    except Exception as e:
        return f"<html><body><h3>Error rendering document: {html.escape(str(e))}</h3></body></html>"


# ── GET /cases/{id}/view-source — view the main file inline ──────────────────

@router.get("/{case_id}/view-source")
def view_case_source_file(
    case_id: int,
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(verify_token_from_anywhere)
):
    from fastapi.responses import FileResponse, HTMLResponse
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    safe_path = get_safe_file_path(case.file_path, case.source_folder)
    
    if safe_path.lower().endswith(".docx"):
        html_content = convert_docx_to_html(safe_path, search)
        return HTMLResponse(
            content=html_content,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
        
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
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(verify_token_from_anywhere)
):
    from fastapi.responses import FileResponse, HTMLResponse
    case_file = db.query(CaseFile).filter(CaseFile.id == file_id).first()
    if not case_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    case = db.query(Case).filter(Case.id == case_file.case_id).first()
    source_folder = case.source_folder if case else None
    
    safe_path = get_safe_file_path(case_file.file_path, source_folder)
    
    if safe_path.lower().endswith(".docx"):
        html_content = convert_docx_to_html(safe_path, search)
        return HTMLResponse(
            content=html_content,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
        
    mime_type, _ = mimetypes.guess_type(safe_path)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    return FileResponse(
        path=safe_path,
        media_type=mime_type,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )