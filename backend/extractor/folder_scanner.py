import os
from extractor.detect import is_allowed, detect_file_type, extract_text
from extractor.field_parser import parse_fields, count_extracted_fields
from validator import validate_extraction
from datetime import datetime

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png"}


def get_case_folders(root_path: str) -> list[dict]:
    """
    Walk the root path and find all case folders.
    Structure: root/year/Case No-XX-YYYY/
    Returns list of {case_name, case_path}
    """
    case_folders = []

    if not os.path.exists(root_path):
        raise ValueError(f"Root path does not exist: {root_path}")

    # Walk two levels deep: year/ → case folder/
    for year_entry in os.scandir(root_path):
        if not year_entry.is_dir():
            continue
        for case_entry in os.scandir(year_entry.path):
            if not case_entry.is_dir():
                continue
            case_folders.append({
                "case_name": case_entry.name,
                "case_path": case_entry.path,
            })

    return case_folders


def collect_files(case_path: str) -> list[dict]:
    """
    Collect all processable files from a case folder.
    - Root level: .pdf, .docx
    - photos/ subfolder: .jpg, .jpeg, .png
    - RDA/ subfolder: .pdf, .docx
    Returns list of {file_path, file_type}
    """
    files = []

    for entry in os.scandir(case_path):
        if entry.is_file():
            ext = os.path.splitext(entry.name)[1].lower()
            if ext in {".pdf", ".docx"}:
                files.append({
                    "file_path": entry.path,
                    "file_type": detect_file_type(entry.name)
                })
        elif entry.is_dir() and entry.name.lower() == "photos":
            # Scan photos subfolder for images
            for photo_entry in os.scandir(entry.path):
                if photo_entry.is_file():
                    ext = os.path.splitext(photo_entry.name)[1].lower()
                    if ext in {".jpg", ".jpeg", ".png"}:
                        files.append({
                            "file_path": photo_entry.path,
                            "file_type": "image"
                        })
        elif entry.is_dir() and entry.name.lower() == "rda":
            # Scan RDA subfolder for documents (.pdf, .docx)
            for rda_entry in os.scandir(entry.path):
                if rda_entry.is_file():
                    ext = os.path.splitext(rda_entry.name)[1].lower()
                    if ext in {".pdf", ".docx"}:
                        files.append({
                            "file_path": rda_entry.path,
                            "file_type": detect_file_type(rda_entry.name)
                        })

    return files


def process_case_folder(case_name: str, case_path: str) -> dict:
    """
    Process all files in a case folder.
    Tracks per-file extraction AND merges text for field extraction.
    Returns a dict with case data + a list of file records.
    """
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
        "officer": fields.get("officer"),
        "date": fields.get("date"),
        "location": fields.get("location"),
        "incident_type": fields.get("incident_type"),
        "complainant": fields.get("complainant"),
        "suspect": fields.get("suspect"),
        "evidence": fields.get("evidence"),
        "notes": fields.get("notes"),
        "ocr_confidence": avg_ocr_confidence,
        "fields_extracted": count_extracted_fields(fields),
        "error_flag": error_flag,
        "error_reason": error_reason,
        "file_records": file_records,  # ← NEW
    }

def get_folder_fingerprint(case_path: str) -> dict:
    """
    Compute a fingerprint of a case folder's contents:
    file count + latest modification time across all relevant files
    (root level docs + photos/ subfolder images).
    """
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