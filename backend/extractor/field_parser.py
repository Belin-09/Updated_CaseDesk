import re
from typing import Optional

# Try to load spaCy — it's a fallback, not required
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except Exception:
    SPACY_AVAILABLE = False


# ── Regex Patterns ────────────────────────────────────────────────────────────

PATTERNS = {
    "officer": [
        r"(?:investigating\s+)?officer(?:\s+name)?[\s:–\-]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+)",
        r"(?:officer\s+in\s+charge|OIC)[\s:–\-]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+)",
        r"(?:prepared\s+by|reported\s+by|investigated\s+by)[\s:–\-]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+)",
        r"INVESTIGATOR\s+NAME[\s:–\-]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*)",
    ],
    "date": [
        r"(?:date\s+of\s+incident|incident\s+date|date)[\s:–\-]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        r"(?:date\s+of\s+incident|incident\s+date|date)[\s:–\-]+(\d{1,2}\s+\w+\s+\d{4})",
        r"(?:date\s+of\s+incident|incident\s+date|date)[\s:–\-]+(\w+\s+\d{1,2},?\s+\d{4})",
        r"DATE[\s:–\-]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
    ],
    "location": [
        r"(?:location|place\s+of\s+incident|incident\s+location|address)[\s:–\-]+([A-Za-z0-9\s,\.]+?)(?:\n|$)",
        r"(?:occurred\s+at|took\s+place\s+at|reported\s+at)[\s:–\-]+([A-Za-z0-9\s,\.]+?)(?:\n|$)",
        r"LOCATION[\s:–\-]+([A-Za-z0-9\s,\.]+?)(?:\n|$)",
    ],
    "incident_type": [
        r"(?:incident\s+type|type\s+of\s+incident|nature\s+of\s+(?:incident|case)|offence|offense)[\s:–\-]+([A-Za-z\s]+?)(?:\n|$)",
        r"(?:case\s+type|crime\s+type)[\s:–\-]+([A-Za-z\s]+?)(?:\n|$)",
        r"INCIDENT\s+TYPE[\s:–\-]+([A-Za-z\s]+?)(?:\n|$)",
        r"BRIEF\s+OF\s+THE\s+CASE[\s:–\-]+([A-Za-z\s]+?)(?:\n|$)",
    ],
    "complainant": [
        r"(?:complainant|complaint\s+by|filed\s+by|reported\s+by)[\s:–\-]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+)",
        r"(?:victim|plaintiff)[\s:–\-]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+)",
        r"COMPLAINANT[\s:–\-]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*)",
    ],
    "suspect": [
        r"(?:suspect|accused|alleged|defendant|perpetrator)[\s:–\-]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+)",
        r"(?:name\s+of\s+suspect|suspect\s+name)[\s:–\-]+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+)",
        r"SUSPECT[\s:–\-]+([A-Za-z]+(?:\s[A-Za-z]+)*)",
    ],
    "evidence": [
        r"(?:evidence|exhibits?|items?\s+seized|material\s+evidence)[\s:–\-]+([A-Za-z0-9\s,\.;\-]+?)(?:\n\n|\n[A-Z]|$)",
        r"EVIDENCE[\s:–\-]+([A-Za-z0-9\s,\.;\-]+?)(?:\n\n|\n[A-Z]|$)",
    ],
    "notes": [
        r"(?:notes?|remarks?|additional\s+(?:info|information|details?)|comments?)[\s:–\-]+([A-Za-z0-9\s,\.;\-]+?)(?:\n\n|\n[A-Z]|$)",
        r"NOTES?[\s:–\-]+([A-Za-z0-9\s,\.;\-]+?)(?:\n\n|\n[A-Z]|$)",
    ],
}


# ── Regex Extraction ──────────────────────────────────────────────────────────

def extract_with_regex(field: str, text: str) -> Optional[str]:
    """Try each pattern for a field, return first match."""
    for pattern in PATTERNS[field]:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


# ── spaCy Fallback ────────────────────────────────────────────────────────────

def extract_with_spacy(field: str, text: str) -> Optional[str]:
    """Use spaCy NER as fallback for officer and location."""
    if not SPACY_AVAILABLE:
        return None

    doc = nlp(text[:5000])  # limit for performance

    if field == "officer":
        persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        return persons[0] if persons else None

    if field == "location":
        places = [ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC")]
        return places[0] if places else None

    return None

def clean_value(value: str) -> str:
    """Remove newlines and anything after them from extracted values."""
    if not value:
        return value

    return value.split("\n")[0].strip()

# ── Main Parser ───────────────────────────────────────────────────────────────

def parse_fields(raw_text: str) -> dict:
    """
    Extract all 8 fields from raw text.
    Uses regex first, spaCy fallback for officer and location.
    Returns a dict with all fields (None if not found).
    """
    fields = {}
    spacy_fallback_fields = {"officer", "location"}

    for field in PATTERNS:
        value = extract_with_regex(field, raw_text)

        if value is None and field in spacy_fallback_fields:
            value = extract_with_spacy(field, raw_text)

        fields[field] = clean_value(value) if value else None

    return fields


# ── Field Count Helper ────────────────────────────────────────────────────────

def count_extracted_fields(fields: dict) -> int:
    """Count how many fields were successfully extracted (not None)."""
    return sum(1 for v in fields.values() if v is not None)