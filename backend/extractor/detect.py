import os

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png"}

def detect_file_type(filename: str) -> str:
    """
    Returns file type based on extension.
    Possible values: 'pdf', 'docx', 'image', 'unknown'
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        return "pdf"
    elif ext == ".docx":
        return "docx"
    elif ext in {".jpg", ".jpeg", ".png"}:
        return "image"
    else:
        return "unknown"

def is_allowed(filename: str) -> bool:
    """
    Returns True if file extension is in the allowed list.
    """
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

from extractor.pdf_extractor import extract_from_pdf
from extractor.docx_extractor import extract_from_docx
from extractor.image_extractor import extract_from_image


def extract_text(file_path: str, file_type: str) -> tuple[str, float | None]:
    """
    Unified extraction entry point.
    Returns (raw_text, ocr_confidence or None)
    """
    if file_type == "pdf":
        return extract_from_pdf(file_path)
    elif file_type == "docx":
        return extract_from_docx(file_path)
    elif file_type == "image":
        return extract_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")