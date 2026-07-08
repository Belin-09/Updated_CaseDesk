import os
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models import Case, AuditLog, CaseFile
from auth import get_current_user
from extractor.detect import detect_file_type, is_allowed, extract_text
from extractor.field_parser import parse_fields, count_extracted_fields
from validator import validate_extraction
from extractor.folder_scanner import get_case_folders, process_case_folder, get_folder_fingerprint
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class ScanFolderRequest(BaseModel):
    root_path: str


# ── In-memory scan state (single-process dev setup) ─────────────────────────

scan_state = {
    "active": False,
    "scan_id": None,
    "total": 0,
    "processed": 0,
    "skipped": 0,
    "reprocessed": 0,
    "failed": 0,
    "current_case": None,
    "status": "idle",   # idle | running | completed | failed
    "started_at": None,
    "finished_at": None,
    "cases": [],
    "error": None,
}

scan_lock = threading.Lock()


# ── Manual single-file upload (unchanged — for testing/demos) ───────────────

@router.post("/")
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # 1. Validate extension
    if not is_allowed(file.filename):
        raise HTTPException(
            status_code=400,
            detail="File type not allowed. Accepted: pdf, docx, jpg, jpeg, png"
        )

    # 2. Read + size check
    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 20MB"
        )

    # 3. Save to disk
    ext = os.path.splitext(file.filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    relative_path = f"uploads/{unique_name}"

    with open(file_path, "wb") as f:
        f.write(contents)

    # 4. Detect file type
    file_type = detect_file_type(file.filename)

    # 5. Extract text
    raw_text = ""
    ocr_confidence = None
    extraction_exception = None

    try:
        raw_text, ocr_confidence = extract_text(file_path, file_type)
    except Exception as e:
        import traceback
        print(f"Error extracting text from uploaded file {file.filename}:")
        traceback.print_exc()
        extraction_exception = str(e)

    # 6. Parse fields
    fields = {}
    if not extraction_exception and raw_text:
        try:
            fields = parse_fields(raw_text)
        except Exception as e:
            import traceback
            print(f"Error parsing fields from uploaded file {file.filename}:")
            traceback.print_exc()
            extraction_exception = str(e)

    # 7. Validate
    error_flag, error_reason = validate_extraction(
        raw_text=raw_text,
        fields=fields,
        ocr_confidence=ocr_confidence,
        extraction_exception=extraction_exception
    )

    # 8. Save to DB
    case = Case(
        file_name=file.filename,
        file_path=relative_path,
        uploaded_by=current_user.username,
        raw_text=raw_text,
        incident_type=fields.get("incident_type"),
        status="open",
        error_flag=error_flag,
        error_reason=error_reason,
        analyst=fields.get("analyst"),
        investigating_officer=fields.get("investigating_officer"),
        pertains_service_no=fields.get("pertains_service_no"),
        pertains_name=fields.get("pertains_name"),
        pertains_unit=fields.get("pertains_unit"),
        date_deposition=fields.get("date_deposition"),
        date_issuance=fields.get("date_issuance"),
        date_intimation=fields.get("date_intimation"),
        date_return=fields.get("date_return"),
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Save per-file CaseFile record for source file tracking
    case_file = CaseFile(
        case_id=case.id,
        file_name=file.filename,
        file_path=relative_path,
        file_type=file_type,
        raw_text=raw_text,
        ocr_confidence=str(ocr_confidence) if ocr_confidence is not None else None,
        extraction_error=extraction_exception or (error_reason if error_flag else None),
    )
    db.add(case_file)
    db.commit()

    # 9. Audit log
    log = AuditLog(
        username=current_user.username,
        action="UPLOADED_FILE",
        case_id=case.id,
        details=f"Uploaded {file.filename} ({file_type})"
    )
    db.add(log)
    db.commit()

    # 10. Build response
    return {
        "message": "File processed successfully",
        "case_id": case.id,
        "file_name": file.filename,
        "file_type": file_type,
        "uploaded_by": current_user.username,
        "fields_extracted": count_extracted_fields(fields),
        "error_flag": error_flag,
        "error_reason": error_reason,
        "ocr_confidence": ocr_confidence,
        "extracted_fields": {
            "officer": fields.get("officer"),
            "date": fields.get("date"),
            "location": fields.get("location"),
            "incident_type": fields.get("incident_type"),
            "complainant": fields.get("complainant"),
            "suspect": fields.get("suspect"),
            "evidence": fields.get("evidence"),
            "notes": fields.get("notes"),
        }
    }


# ── Background scan worker ───────────────────────────────────────────────────

def process_single_folder(folder: dict, username: str):
    case_name = folder["case_name"]
    case_path = folder["case_path"]
    is_file = folder.get("is_file", False)
    db = SessionLocal()
    try:
        with scan_lock:
            scan_state["current_case"] = case_name

        fingerprint = get_folder_fingerprint(case_path, is_file)
        existing = db.query(Case).filter(Case.source_folder == case_path).first()

        if existing:
            unchanged = (
                existing.file_count == fingerprint["file_count"]
                and existing.last_modified == fingerprint["last_modified"]
            )
            missing_pertains = (
                existing.pertains_service_no is None
                and existing.pertains_name is None
                and existing.pertains_unit is None
            )
            if unchanged and not missing_pertains:
                with scan_lock:
                    scan_state["skipped"] += 1
                    scan_state["cases"].append({
                        "case_name": case_name,
                        "status": "skipped",
                        "reason": "No changes detected"
                    })
                return

            # Folder changed — reprocess and UPDATE existing case
            data = process_case_folder(case_name, case_path, is_file)

            existing.file_name = data["file_name"]
            existing.raw_text = data["raw_text"]
            existing.incident_type = data["incident_type"]
            existing.command = data.get("command")
            existing.suspected_pio_numbers = data.get("suspected_pio_numbers")
            existing.suspected_pio_count = data.get("suspected_pio_count", 0)
            existing.error_flag = data["error_flag"]
            existing.error_reason = data["error_reason"]
            existing.ocr_confidence = str(data["ocr_confidence"]) if data["ocr_confidence"] is not None else None
            existing.file_count = fingerprint["file_count"]
            existing.last_modified = fingerprint["last_modified"]
            existing.analyst = data.get("analyst")
            existing.investigating_officer = data.get("investigating_officer")
            existing.pertains_service_no = data.get("pertains_service_no")
            existing.pertains_name = data.get("pertains_name")
            existing.pertains_unit = data.get("pertains_unit")

            existing.date_deposition = data.get("date_deposition")
            existing.date_issuance = data.get("date_issuance")
            existing.date_intimation = data.get("date_intimation")
            existing.date_return = data.get("date_return")
            existing.updated_at = datetime.utcnow()

            # Replace old per-file records with fresh ones
            db.query(CaseFile).filter(CaseFile.case_id == existing.id).delete()
            for fr in data["file_records"]:
                db.add(CaseFile(
                    case_id=existing.id,
                    file_name=fr["file_name"],
                    file_path=fr["file_path"],
                    file_type=fr["file_type"],
                    raw_text=fr["raw_text"],
                    ocr_confidence=str(fr["ocr_confidence"]) if fr["ocr_confidence"] is not None else None,
                    extraction_error=fr["extraction_error"],
                ))
            db.commit()

            db.add(AuditLog(
                username=username,
                action="REPROCESSED_FOLDER",
                case_id=existing.id,
                details=f"Reprocessed {case_name} (background scan)"
            ))
            db.commit()

            with scan_lock:
                scan_state["reprocessed"] += 1
                scan_state["cases"].append({
                    "case_name": case_name,
                    "case_id": existing.id,
                    "status": "reprocessed",
                    "fields_extracted": data["fields_extracted"],
                    "error_flag": data["error_flag"],
                    "error_reason": data["error_reason"],
                })

        else:
            # New case folder
            data = process_case_folder(case_name, case_path, is_file)

            case = Case(
                case_name=data["case_name"],
                source_folder=data["source_folder"],
                file_name=data["file_name"],
                file_path=data["file_path"],
                uploaded_by=username,
                raw_text=data["raw_text"],
                incident_type=data["incident_type"],
                command=data.get("command"),
                suspected_pio_numbers=data.get("suspected_pio_numbers"),
                suspected_pio_count=data.get("suspected_pio_count", 0),
                status="open",
                error_flag=data["error_flag"],
                error_reason=data["error_reason"],
                file_count=fingerprint["file_count"],
                last_modified=fingerprint["last_modified"],
                analyst=data.get("analyst"),
                investigating_officer=data.get("investigating_officer"),
                pertains_service_no=data.get("pertains_service_no"),
                pertains_name=data.get("pertains_name"),
                pertains_unit=data.get("pertains_unit"),

                date_deposition=data.get("date_deposition"),
                date_issuance=data.get("date_issuance"),
                date_intimation=data.get("date_intimation"),
                date_return=data.get("date_return"),
            )
            db.add(case)
            db.commit()
            db.refresh(case)

            for fr in data["file_records"]:
                db.add(CaseFile(
                    case_id=case.id,
                    file_name=fr["file_name"],
                    file_path=fr["file_path"],
                    file_type=fr["file_type"],
                    raw_text=fr["raw_text"],
                    ocr_confidence=str(fr["ocr_confidence"]) if fr["ocr_confidence"] is not None else None,
                    extraction_error=fr["extraction_error"],
                ))
            db.commit()

            db.add(AuditLog(
                username=username,
                action="SCANNED_FOLDER",
                case_id=case.id,
                details=f"Scanned {case_name} (background scan)"
            ))
            db.commit()

            with scan_lock:
                scan_state["processed"] += 1
                scan_state["cases"].append({
                    "case_name": case_name,
                    "case_id": case.id,
                    "status": "processed",
                    "fields_extracted": data["fields_extracted"],
                    "error_flag": data["error_flag"],
                    "error_reason": data["error_reason"],
                })

    except Exception as e:
        db.rollback()
        with scan_lock:
            scan_state["failed"] += 1
            scan_state["cases"].append({
                "case_name": case_name,
                "status": "failed",
                "reason": str(e)
            })
    finally:
        db.close()


def run_folder_scan(root_path: str, username: str, scan_id: str):
    """
    Runs in the background via BackgroundTasks.
    Uses ThreadPoolExecutor to process folders concurrently.
    """
    try:
        case_folders = get_case_folders(root_path)

        with scan_lock:
            scan_state["total"] = len(case_folders)

        # Calculate optimal worker threads count
        num_workers = min(4, os.cpu_count() or 2)

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(process_single_folder, folder, username)
                for folder in case_folders
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error executing scan thread task: {e}")

        with scan_lock:
            scan_state["status"] = "completed"
            scan_state["active"] = False
            scan_state["current_case"] = None
            scan_state["finished_at"] = datetime.utcnow().isoformat()

    except Exception as e:
        with scan_lock:
            scan_state["status"] = "failed"
            scan_state["active"] = False
            scan_state["error"] = str(e)
            scan_state["finished_at"] = datetime.utcnow().isoformat()


# ── Scan-folder endpoint — starts background job, returns immediately ───────

@router.post("/scan-folder")
def scan_folder(
    payload: ScanFolderRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user)
):
    root_path = payload.root_path
    if not root_path:
        raise HTTPException(status_code=400, detail="root_path is required")

    if not os.path.exists(root_path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {root_path}")

    with scan_lock:
        if scan_state["active"]:
            raise HTTPException(
                status_code=409,
                detail="A scan is already in progress. Please wait for it to finish."
            )

        scan_id = str(uuid.uuid4())
        scan_state.update({
            "active": True,
            "scan_id": scan_id,
            "total": 0,
            "processed": 0,
            "skipped": 0,
            "reprocessed": 0,
            "failed": 0,
            "current_case": None,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "cases": [],
            "error": None,
        })

    background_tasks.add_task(run_folder_scan, root_path, current_user.username, scan_id)

    return {
        "message": "Scan started",
        "scan_id": scan_id
    }


# ── Poll scan progress ────────────────────────────────────────────────────

@router.get("/scan-status")
def get_scan_status(current_user=Depends(get_current_user)):
    with scan_lock:
        return dict(scan_state)


# ── Local folder picker dialog ─────────────────────────────────────────────

@router.post("/select-folder")
def select_folder(current_user=Depends(get_current_user)):
    """
    Open a native directory dialog on the server's local machine (since the app runs locally).
    Returns the selected folder path, or null if cancelled / unsupported.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # Hide main window
        root.attributes("-topmost", True)
        folder_path = filedialog.askdirectory(parent=root, title="Select Cases Root Folder")
        root.destroy()
        
        return {"folder_path": folder_path if folder_path else None, "success": True}
    except Exception as e:
        print(f"Tkinter folder picker warning: {e}")
        return {
            "folder_path": None,
            "success": False,
            "message": "Native folder picker is unavailable. Please enter or paste the folder path manually."
        }