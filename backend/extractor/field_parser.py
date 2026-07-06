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

# ── Custom Field Extractors ──────────────────────────────────────────────

COMMAND_KEYWORDS = [
    ("North Eastern", [r"north\s*eastern\s*(?:command|comd)?", r"\bne\s+comd\b"]),
    ("South Western", [r"south\s*western\s*(?:command|comd)?", r"\bsw\s+comd\b"]),
    ("Central", [r"central\s+(?:command|comd)", r"\bcentral\b"]),
    ("Northern", [r"northern\s+(?:command|comd)", r"\bnorthern\b"]),
    ("Southern", [r"southern\s+(?:command|comd)", r"\bsouthern\b"]),
    ("Eastern", [r"eastern\s+(?:command|comd)", r"\beastern\b"]),
    ("Western", [r"western\s+(?:command|comd)", r"\bwestern\b"]),
]

def extract_command(text: str) -> Optional[str]:
    """Identify military command from text."""
    if not text:
        return None
    for cmd_name, patterns in COMMAND_KEYWORDS:
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return cmd_name
    return None

def extract_suspected_pio_numbers(text: str) -> tuple[str, int]:
    """Find phone numbers following 'Suspected PIO' / 'Suspect PIO' / 'PIO'."""
    if not text:
        return "", 0
    patterns = [
        r"(?:suspected\s+pio|suspect\s+pio|pio\s*(?:no|number)?|pio\s+mobile)[\s:–\-]*(\+?\d[\d\s\-]{8,14}\d)",
        r"(?:suspected\s+pio|suspect\s+pio)[\s\w]*?(\+?\d{10,12})"
    ]
    found_numbers = set()
    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            raw_num = re.sub(r"[^\d+]", "", match.group(1))
            if len(raw_num) >= 10:
                found_numbers.add(raw_num)

    numbers_str = ", ".join(sorted(found_numbers))
    return numbers_str, len(found_numbers)

def classify_case_type(raw_text: str, extracted_type: Optional[str]) -> str:
    """Classify case into Int (Cyber Espionage), Int (Social Media violation), or DV / Misc."""
    combined = f"{extracted_type or ''} {raw_text or ''}".lower()
    if re.search(r"cyber\s*espionage|espionage|cyber\s*attack", combined):
        return "Int (Cyber Espionage)"
    if re.search(r"social\s*media|whatsapp|facebook|telegram|instagram|honeytrap", combined):
        return "Int (Social Media violation)"
    return "DV / Misc"

def extract_pertains_service_no(text: str) -> Optional[str]:
    """Extract military service/army number (e.g. IC-72314X, SS-12345, 12345678A)."""
    if not text:
        return None
    patterns = [
        r"(?:service\s+no|army\s+no|personal\s+no|no\.?)[\s:–\-]+([A-Z]{2,3}[\-\s]?\d{5,6}[A-Z]?|\d{7,8}[A-Z]?)",
        r"\b([A-Z]{2,3}[\-\s]?\d{5,6}[A-Z]?|\d{7,8}[A-Z])\b"
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def extract_pertains_name(text: str) -> Optional[str]:
    """Extract officer name under pertains-to or rank search."""
    if not text:
        return None
    patterns = [
        r"(?:pertains\s+to|Pertains\s+to|PERTAINS\s+TO|name|Name|NAME|offr|Offr|OFFR|officer|Officer|OFFICER)[\s:–\-]+(?:(?:Lt\s+Col|Col|Major|Capt|Lt|Sub|Hav|Nk|L/Nk|Sep|Col|Brig|Maj\s+Gen|Gen|Havildar|Naik|Sepoy|lt\s+col|col|major|capt|lt|sub|hav|nk|l/nk|sep|havildar|naik|sepoy)\s+)?([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+)",
        r"\b(?:Lt\s+Col|Col|Major|Capt|Lt|Sub|Hav|Nk|L/Nk|Sep|Havildar|Naik|Sepoy|lt\s+col|col|major|capt|lt|sub|hav|nk|l/nk|sep|havildar|naik|sepoy)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*)\b"
    ]
    for pat in patterns:
        match = re.search(pat, text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None

def extract_pertains_unit(text: str) -> Optional[str]:
    """Extract unit name (e.g. 12 Engrs, 123 Field Regt, HQ 12 Corps)."""
    if not text:
        return None
    patterns = [
        r"(?:unit)[\s:–\-]+([A-Za-z0-9\s\(\)\-\.,]+?)(?:\n|$)",
        r"\b(\d{1,4}\s+(?:Engrs|Arty|Inf\s+Bn|Regt|Signal|Fd\s+Regt|Sikh|Jat|Rajput|Kumaon|Garh\s+Rif|Assam|Mahar|JAK\s+RIF|JAK\s+LI|Para|Gorkha|Armd\s+Regt|Cav|ASC|AMC|AOC|EME))\b"
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def extract_ro_pattern(text: str) -> Optional[dict]:
    """
    Extract pertains Service No, Name, and Unit matching the R/O pattern:
    e.g. 'CYBER FORENSIC INVESTIGATION IN R/O 047588 NB SUB HARISH OF ABC (CASE NO-04)'
    """
    if not text:
        return None
    pattern = r"\br/o\s+([A-Z0-9\-\s]{4,15}?)\s+([^of\n]+?)\s+of\s+([^(\n]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        service_no = match.group(1).strip()
        name = match.group(2).strip()
        unit = match.group(3).strip()
        
        name = re.sub(r"\s+", " ", name)
        unit = re.sub(r"\s+", " ", unit)
        
        if service_no and name and unit:
            return {
                "pertains_service_no": service_no,
                "pertains_name": name,
                "pertains_unit": unit
            }
    return None

# ── Main Parser ───────────────────────────────────────────────────────────────

def parse_fields(raw_text: str) -> dict:
    """
    Extract all fields from raw text including Command, PIO numbers, and Case Type.
    """
    fields = {}
    spacy_fallback_fields = {"officer", "location"}

    for field in PATTERNS:
        value = extract_with_regex(field, raw_text)

        if value is None and field in spacy_fallback_fields:
            value = extract_with_spacy(field, raw_text)

        fields[field] = clean_value(value) if value else None

    # Custom Analytics fields
    fields["command"] = extract_command(raw_text)
    pio_str, pio_count = extract_suspected_pio_numbers(raw_text)
    fields["suspected_pio_numbers"] = pio_str
    fields["suspected_pio_count"] = pio_count
    fields["incident_type"] = classify_case_type(raw_text, fields.get("incident_type"))

    # Custom pertains-to fields
    ro_data = extract_ro_pattern(raw_text)
    if ro_data:
        fields["pertains_service_no"] = ro_data["pertains_service_no"]
        fields["pertains_name"] = ro_data["pertains_name"]
        fields["pertains_unit"] = ro_data["pertains_unit"]
    else:
        fields["pertains_service_no"] = extract_pertains_service_no(raw_text)
        fields["pertains_name"] = extract_pertains_name(raw_text)
        fields["pertains_unit"] = extract_pertains_unit(raw_text)
        
    fields["analyst"] = None
    fields["investigating_officer"] = None
    fields["date_receiving"] = None
    fields["date_completion"] = None
    fields["date_dispatch"] = None

    return fields


# ── Field Count Helper ────────────────────────────────────────────────────────

def count_extracted_fields(fields: dict) -> int:
    """Count how many fields were successfully extracted (not None)."""
    extractable_fields = ["pertains_service_no", "pertains_name", "pertains_unit"]
    return sum(1 for k in extractable_fields if fields.get(k) is not None)