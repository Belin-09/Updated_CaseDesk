from extractor.field_parser import count_extracted_fields

# Thresholds
MIN_FIELDS_REQUIRED = 3
MIN_OCR_CONFIDENCE = 60.0


def validate_extraction(
    raw_text: str,
    fields: dict,
    ocr_confidence: float | None = None,
    extraction_exception: str | None = None
) -> tuple[bool, str | None]:
    """
    Run post-extraction checks.
    Returns (error_flag, error_reason)
    
    error_flag = True means case needs manual review.
    error_reason is one of:
        EMPTY_TEXT
        LOW_FIELDS
        LOW_OCR_CONFIDENCE
        EXTRACTION_EXCEPTION
    """

    # Check 1 — extraction crashed
    if extraction_exception:
        return True, f"EXTRACTION_EXCEPTION: {extraction_exception}"

    # Check 2 — no text extracted at all
    if not raw_text or not raw_text.strip():
        return True, "EMPTY_TEXT"

    # Check 3 — OCR confidence too low
    if ocr_confidence is not None and ocr_confidence < MIN_OCR_CONFIDENCE:
        return True, "LOW_OCR_CONFIDENCE"

    # Check 4 — too few fields extracted
    field_count = count_extracted_fields(fields)
    if field_count < MIN_FIELDS_REQUIRED:
        return True, "LOW_FIELDS"

    # All checks passed
    return False, None