import os
from extractor.detect import is_allowed, detect_file_type, extract_text
from extractor.field_parser import parse_fields, count_extracted_fields
from validator import validate_extraction
from datetime import datetime

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png"}


def is_year_dir(path: str) -> bool:
    """Check if directory name is a 4-digit year container (e.g. 2020, 2026)."""
    name = os.path.basename(path.rstrip(r"\/"))
    return name.isdigit() and len(name) == 4


def is_container_dir(path: str) -> bool:
    """Check if directory is a container holding year folders or case folders."""
    if is_year_dir(path):
        return True
    try:
        for entry in os.scandir(path):
            if entry.is_dir():
                if is_year_dir(entry.path) or entry.name.lower().startswith("case") or "case" in entry.name.lower():
                    return True
    except Exception:
        pass
    return False


def get_case_folders(root_path: str) -> list[dict]:
    """
    Walk the root path and find all case folders.
    Rules:
    - Loose files directly under a container folder (like case_data) are ignored.
    - Subfolders inside a year container (e.g. 2026) are treated as case folders.
    - Folder names (e.g. 'Case No-01-2026' or 'Lt Col abc of xyz') are used as case_name.
    - Single case folder input is handled directly.
    Returns list of {case_name, case_path, is_file}
    """
    case_folders = []

    if not os.path.exists(root_path):
        raise ValueError(f"Root path does not exist: {root_path}")

    # Single standalone file selected directly by user
    if os.path.isfile(root_path):
        ext = os.path.splitext(root_path)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            case_folders.append({
                "case_name": os.path.basename(root_path),
                "case_path": root_path,
                "is_file": True
            })
        return case_folders

    # If input is directly a year directory (e.g. E:\case_data\2026)
    if is_year_dir(root_path):
        for entry in os.scandir(root_path):
            if entry.is_dir():
                case_folders.append({
                    "case_name": entry.name,
                    "case_path": entry.path,
                    "is_file": False
                })
        return case_folders

    # Check if root_path is a single case folder (not a container)
    if not is_container_dir(root_path):
        case_folders.append({
            "case_name": os.path.basename(root_path),
            "case_path": root_path,
            "is_file": False
        })
        return case_folders

    # Otherwise root_path is a container directory (e.g. E:\case_data)
    # Loose files directly under case_data are ignored per requirement.
    for entry in os.scandir(root_path):
        if entry.is_dir():
            if is_year_dir(entry.path):
                # entry is a year container (e.g. 2026), dive 1 level deep for cases
                for case_entry in os.scandir(entry.path):
                    if case_entry.is_dir():
                        case_folders.append({
                            "case_name": case_entry.name,
                            "case_path": case_entry.path,
                            "is_file": False
                        })
            else:
                # entry is a case folder directly under root_path
                case_folders.append({
                    "case_name": entry.name,
                    "case_path": entry.path,
                    "is_file": False
                })

    return case_folders


def collect_files(case_path: str) -> list[dict]:
    """
    Collect all processable files from a case folder recursively.
    Traverses all subdirectories and collects:
    - .pdf, .docx (treated as document files)
    - .jpg, .jpeg, .png (treated as image files)
    Returns list of {file_path, file_type}
    """
    files = []

    for root, dirs, filenames in os.walk(case_path):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in {".pdf", ".docx"}:
                files.append({
                    "file_path": os.path.join(root, filename),
                    "file_type": detect_file_type(filename)
                })
            elif ext in {".jpg", ".jpeg", ".png"}:
                files.append({
                    "file_path": os.path.join(root, filename),
                    "file_type": "image"
                })

    return files


def process_case_folder(case_name: str, case_path: str, is_file: bool = False) -> dict:
    """
    Process all files in a case folder or a standalone file.
    Tracks per-file extraction AND merges text for field extraction.
    Returns a dict with case data + a list of file records.
    """
    if is_file:
        files = [{
            "file_path": case_path,
            "file_type": detect_file_type(case_name)
        }]
    else:
        files = collect_files(case_path)

    merged_text = ""
    ocr_confidences = []
    extraction_exception = None
    file_names = []
    file_records = []  # ← NEW: per-file tracking

    for f in files:
        fname = os.path.basename(f["file_path"])
        file_names.append(fname)

        file_text = ""
        file_confidence = None
        file_error = None

        try:
            file_text, file_confidence = extract_text(f["file_path"], f["file_type"])
            if file_text:
                merged_text += f"\n\n--- {fname} ---\n{file_text}"
            if file_confidence is not None:
                ocr_confidences.append(file_confidence)
        except Exception as e:
            file_error = str(e)
            extraction_exception = file_error  # last failure, surfaced at case level too

        file_records.append({
            "file_name": fname,
            "file_path": f["file_path"],
            "file_type": f["file_type"],
            "raw_text": file_text.strip() if file_text else None,
            "ocr_confidence": file_confidence,
            "extraction_error": file_error,
        })

    avg_ocr_confidence = (
        round(sum(ocr_confidences) / len(ocr_confidences), 2)
        if ocr_confidences else None
    )

    fields = {}
    if merged_text.strip():
        try:
            fields = parse_fields(merged_text)
        except Exception as e:
            extraction_exception = str(e)

    error_flag, error_reason = validate_extraction(
        raw_text=merged_text,
        fields=fields,
        ocr_confidence=avg_ocr_confidence,
        extraction_exception=extraction_exception
    )

    return {
        "case_name": case_name,
        "source_folder": case_path,
        "file_name": ", ".join(file_names),
        "file_path": case_path,
        "raw_text": merged_text.strip(),
        "incident_type": fields.get("incident_type"),
        "command": fields.get("command"),
        "suspected_pio_numbers": fields.get("suspected_pio_numbers"),
        "suspected_pio_count": fields.get("suspected_pio_count", 0),
        "analyst": fields.get("analyst"),
        "investigating_officer": fields.get("investigating_officer"),
        "pertains_service_no": fields.get("pertains_service_no"),
        "pertains_name": fields.get("pertains_name"),
        "pertains_unit": fields.get("pertains_unit"),
        "date_deposition": fields.get("date_deposition"),
        "date_issuance": fields.get("date_issuance"),
        "date_intimation": fields.get("date_intimation"),
        "date_return": fields.get("date_return"),
        "ocr_confidence": avg_ocr_confidence,
        "fields_extracted": count_extracted_fields(fields),
        "error_flag": error_flag,
        "error_reason": error_reason,
        "file_records": file_records,
    }

def get_folder_fingerprint(case_path: str, is_file: bool = False) -> dict:
    """
    Compute a fingerprint of a case folder's (or standalone file's) contents:
    file count + latest modification time across all relevant files.
    """
    if is_file:
        try:
            mtime = os.path.getmtime(case_path)
            last_modified = datetime.fromtimestamp(mtime).replace(microsecond=0)
            return {
                "file_count": 1,
                "last_modified": last_modified
            }
        except OSError:
            return {
                "file_count": 1,
                "last_modified": None
            }

    files = collect_files(case_path)

    file_count = len(files)
    latest_mtime = None

    for f in files:
        try:
            mtime = os.path.getmtime(f["file_path"])
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime = mtime
        except OSError:
            continue

    last_modified = (
        datetime.fromtimestamp(latest_mtime).replace(microsecond=0)
        if latest_mtime else None
    )

    return {
        "file_count": file_count,
        "last_modified": last_modified
    }