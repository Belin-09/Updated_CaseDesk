import re
from typing import Optional




# ── Regex Patterns ────────────────────────────────────────────────────────────

PATTERNS = {
    "incident_type": [
        r"(?:incident\s+type|type\s+of\s+incident|nature\s+of\s+(?:incident|case)|offence|offense)[\s:–\-]+([A-Za-z\s]+?)(?:\n|$)",
        r"(?:case\s+type|crime\s+type)[\s:–\-]+([A-Za-z\s]+?)(?:\n|$)",
        r"INCIDENT\s+TYPE[\s:–\-]+([A-Za-z\s]+?)(?:\n|$)",
        r"BRIEF\s+OF\s+THE\s+CASE[\s:–\-]+([A-Za-z\s]+?)(?:\n|$)",
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




def clean_value(value: str) -> str:
    """Remove newlines and anything after them from extracted values."""
    if not value:
        return value

    return value.split("\n")[0].strip()

# ── Custom Field Extractors ──────────────────────────────────────────────

COMMAND_KEYWORDS = [
    ("ARTRAC", [r"army\s*training\s*command", r"\bartrac\b", r"\bar\s*trg\s*comd\b"]),
    ("South Western", [r"south\s*(?:western|west)\s*(?:command|comd)?", r"\bsw\s+comd\b"]),
    ("Central", [r"(?:central|centre)\s+(?:command|comd)", r"\b(?:central|centre)\b"]),
    ("Northern", [r"(?:northern|north)\s+(?:command|comd)", r"\b(?:northern|north)\b"]),
    ("Southern", [r"(?:southern|south)\s+(?:command|comd)", r"\b(?:southern|south)\b"]),
    ("Eastern", [r"(?:eastern|east)\s+(?:command|comd)", r"(?<!north\s)\b(?:eastern|east)\b"]),
    ("Western", [r"(?:western|west)\s+(?:command|comd)", r"(?<!south\s)\b(?:western|west)\b"]),
]

def extract_command(hash_text: str) -> Optional[str]:
    """Identify military command from 'Copy to' block in the hash letter."""
    if not hash_text:
        return None
    lines = hash_text.split("\n")
    copy_idx = -1
    for i, line in enumerate(lines):
        if "copy to" in line.lower():
            copy_idx = i
            break
    if copy_idx != -1:
        subsequent_text = "\n".join(lines[copy_idx+1 : copy_idx+7])
        for cmd_name, patterns in COMMAND_KEYWORDS:
            for pat in patterns:
                if re.search(pat, subsequent_text, re.IGNORECASE):
                    return cmd_name
    return None

def extract_suspected_pio_numbers(text: str) -> tuple[str, int]:
    """Find phone numbers following 'Suspected PIO' / 'Suspect PIO' / 'PIO'."""
    if not text:
        return "", 0
    patterns = [
        r"(?:suspected\s+pio|suspect\s+pio|pio\s*(?:no|number)?|pio\s+mobile|pio\s+contact|suspected\s+pio\s+contact|suspect|suspected)[\s:–\-'\"`]*([+()\s]*\d[\d\s\-()]{7,18}\d)",
        r"(?:suspected\s+pio|suspect\s+pio|pio|suspect|suspected)[\s\w:\-'\"`]*?([+()\s]*\d[\d\s\-()]{7,18}\d)"
    ]
    found_numbers = set()
    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            # Extract only digits from the matched string
            clean_digits = re.sub(r"\D", "", match.group(1))
            
            # Skip likely IMEI numbers (which are exactly 15 digits long)
            if len(clean_digits) == 15:
                continue
                
            if len(clean_digits) >= 10:
                # Take only the last 10 digits as the core phone number
                found_numbers.add(clean_digits[-10:])

    numbers_str = ", ".join(sorted(found_numbers))
    return numbers_str, len(found_numbers)

def classify_case_type(covering_text: str) -> str:
    """Classify case based on covering letter text under 'a case of' phrase."""
    if not covering_text:
        return "DV / Misc"
    
    match = re.search(r"a\s+case\s+of\s+(.+)", covering_text, re.IGNORECASE)
    if match:
        after_text = match.group(1).lower()
        if "cyber espionage" in after_text or "espionage" in after_text:
            return "Int (Cyber Espionage)"
        if "social media" in after_text or "honeytrap" in after_text:
            return "Int (Social Media violation)"
            
    return "DV / Misc"

def extract_pertains_service_no(text: str) -> Optional[str]:
    """Extract military service/army number (e.g. IC-72314X, SS-12345, 12345678A)."""
    if not text:
        return None
    patterns = [
        r"(?:service\s+no|army\s+no|personal\s+no|no\.?)[\s:–\-]+([A-Z]{2,3}[\-\s\/]?\d{5,6}[A-Z]?|\d{7,8}[A-Z]?)",
        r"\b([A-Z]{2,3}[\-\s\/]?\d{5,6}[A-Z]?|\d{7,8}[A-Z])\b"
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
    Extract pertains Service No, Name, and Unit matching the R/O pattern or CFI pattern:
    e.g. 'CYBER FORENSIC INVESTIGATION IN R/O 047588 NB SUB HARISH OF ABC (CASE NO-04)'
    e.g. 'PERMISSION FOR CFI: 12345678A RANK NAME OF UNIT'
    """
    if not text:
        return None
        
    patterns = [
        r"\br/o\s+([A-Z0-9\-\/\s\n]{4,25}?)\s+([\s\S]{1,60}?)\s+of\s+([\s\S]{1,100}?)(?:\s+of\s+|\n|\(|case\b|$)",
        r"PERMISSION\s+FOR\s+CFI:\s+([A-Z0-9\-\/\s\n]{4,25}?)\s+([\s\S]{1,60}?)\s+OF\s+([\s\S]{1,100}?)(?:\s+OF\s+|\n|\(|case\b|$)"
    ]
    
    for pattern in patterns:
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
                
    # Fallback: Capture everything after R/O up to "(CASE NO" or "Refs:"
    fallback_pattern = r"\br/o\s+([\s\S]+?)\s*(?:\(\s*case\s*no\b|refs\s*:)"
    fallback_match = re.search(fallback_pattern, text, re.IGNORECASE)
    if fallback_match:
        extracted = fallback_match.group(1).strip()
        extracted = re.sub(r"\s+", " ", extracted) # Clean up newlines
        return {
            "pertains_service_no": None,
            "pertains_name": extracted,
            "pertains_unit": None
        }

    return None

def split_merged_text_by_file(merged_text: str) -> dict:
    if not merged_text:
        return {}
    pattern = r"\n\n--- (.+?) ---\n"
    parts = re.split(pattern, "\n\n" + merged_text)
    files_dict = {}
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            filename = parts[i].strip().lower()
            content = parts[i+1] if i+1 < len(parts) else ""
            files_dict[filename] = content.strip()
    else:
        files_dict["unnamed"] = merged_text.strip()
    return files_dict

def extract_analyst_name(files_dict: dict) -> Optional[str]:
    invalid_keywords = ["see ", "case", "ref", "annexure", "encl", "appx", "appendix", "para"]
    for fname, text in files_dict.items():
        if "noting" in fname and "sheet" in fname:
            lines = text.split("\n")
            for i, line in enumerate(lines):
                lower_line = line.lower()
                if "digital forensic analyst" in lower_line:
                    for j in range(i, max(-1, i - 5), -1):
                        m = re.search(r"\(\s*([A-Za-z\s\.\-]+?)\s*\)", lines[j])
                        if m:
                            val = m.group(1).strip()
                            if val and len(val) >= 3 and len(val) <= 40 and len(lines[j].strip()) <= len(val) + 10 and not any(k in val.lower() for k in invalid_keywords):
                                return val
                elif "pu for perusal, tech review and approval" in lower_line or "tech review and approval pl" in lower_line:
                    for j in range(i, min(len(lines), i + 6)):
                        m = re.search(r"\(\s*([A-Za-z\s\.\-]+?)\s*\)", lines[j])
                        if m:
                            val = m.group(1).strip()
                            if val and len(val) >= 3 and len(val) <= 40 and len(lines[j].strip()) <= len(val) + 10 and not any(k in val.lower() for k in invalid_keywords):
                                return val
    return None

def extract_investigating_officer(files_dict: dict) -> Optional[str]:
    io_keywords = ["investigating officer", "investigating offr", "inv officer", "oic cyber forensic lab", "oic, cyber forensic lab"]
    for fname, text in files_dict.items():
        if "covering" in fname and "letter" in fname:
            lines = text.split("\n")
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                lower_line = line.lower()
                if any(k in lower_line for k in io_keywords):
                    rank = None
                    name = None
                    rank_idx = -1
                    ranks_regex = r"\b(Lt\s+Col|Col|Major|Maj|Capt|Lt|Brig|Maj\s+Gen|Gen|Lt-Col|Lt\.?\s*Col\.?)\b"
                    for j in range(i, max(-1, i - 6), -1):
                        m_rank = re.search(ranks_regex, lines[j], re.IGNORECASE)
                        if m_rank:
                            rank = m_rank.group(1).strip()
                            rank_idx = j
                            break
                    if rank_idx != -1:
                        for k in range(rank_idx, max(-1, rank_idx - 5), -1):
                            m_name = re.search(r"\(\s*([A-Za-z\s\.\-]+?)\s*\)", lines[k])
                            if m_name:
                                name = m_name.group(1).strip()
                                break
                    else:
                        for k in range(i, max(-1, i - 6), -1):
                            m_name = re.search(r"\(\s*([A-Za-z\s\.\-]+?)\s*\)", lines[k])
                            if m_name:
                                name = m_name.group(1).strip()
                                break
                    if rank and name:
                        if name.lower().startswith(rank.lower()):
                            return name
                        return f"{rank} {name}"
                    elif name:
                        return name
                    elif rank:
                        return rank
            
            # Fallback: if no title was found, scan the last 20 lines upwards for a rank + bracketed name
            ranks_regex = r"\b(Lt\s+Col|Col|Major|Maj|Capt|Lt|Brig|Maj\s+Gen|Gen|Lt-Col|Lt\.?\s*Col\.?)\b"
            for i in range(len(lines) - 1, max(-1, len(lines) - 25), -1):
                m_rank = re.search(ranks_regex, lines[i], re.IGNORECASE)
                if m_rank:
                    rank = m_rank.group(1).strip()
                    name = None
                    # Check for bracketed name on the exact same line, or up to 4 lines above it
                    for k in range(i, max(-1, i - 5), -1):
                        m_name = re.search(r"\(\s*([A-Za-z\s\.\-]+?)\s*\)", lines[k])
                        if m_name:
                            name = m_name.group(1).strip()
                            break
                    
                    # Only return if BOTH rank and bracketed name are found to avoid false positives
                    if rank and name:
                        if name.lower().startswith(rank.lower()):
                            return name
                        return f"{rank} {name}"
                        
    return None

def extract_deposition_date(hash_text: str) -> Optional[str]:
    if not hash_text:
        return None
    # Check for point number 2., then take date between "on" and "at"
    pattern = r"\b2\..*?\bon\b\s+(.+?)\s+\bat\b"
    m = re.search(pattern, hash_text, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return None

def extract_issuance_date(return_doc_text: str) -> Optional[str]:
    if not return_doc_text:
        return None
    patterns = [
        r"taken\s+over\s+.*?\s+on\s+(\d{1,2}\s+[A-Za-z]{3,10}\s+\d{4})",
        r"taken\s+over\s+.*?\s+on\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})"
    ]
    for pat in patterns:
        m = re.search(pat, return_doc_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None

def extract_intimation_date(return_doc_text: str) -> Optional[str]:
    if not return_doc_text:
        return None
    patterns = [
        r"1\.1\s+.*?dt\s+(\d{1,2}\s+[A-Za-z]{3,10}\s+\d{4})",
        r"1\.1\s+.*?dt\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        r"refs\b.*?dt\s+(\d{1,2}\s+[A-Za-z]{3,10}\s+\d{4})"
    ]
    for pat in patterns:
        m = re.search(pat, return_doc_text, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
    return None

# ── Main Parser ───────────────────────────────────────────────────────────────

def parse_fields(raw_text: str) -> dict:
    """
    Extract all fields from raw text including Command, PIO numbers, and Case Type.
    """
    # Segment documents first
    files_dict = split_merged_text_by_file(raw_text)

    # 1. Covering Letter (for case classification)
    covering_text = ""
    for fname, txt in files_dict.items():
        if "covering" in fname and "letter" in fname:
            covering_text = txt
            break

    # 2. Hash Letter (for command and pertains/deposition date)
    hash_text = ""
    for fname, txt in files_dict.items():
        if "hash" in fname and "letter" in fname:
            hash_text = txt
            break

    fields = {}

    # Custom Analytics fields
    fields["command"] = extract_command(hash_text)
    
    pio_str, pio_count = extract_suspected_pio_numbers(raw_text)
    fields["suspected_pio_numbers"] = pio_str
    fields["suspected_pio_count"] = pio_count
    
    fields["incident_type"] = classify_case_type(covering_text)

    # 3. Analyst Name
    fields["analyst"] = extract_analyst_name(files_dict)

    # 4. Investigating Officer
    fields["investigating_officer"] = extract_investigating_officer(files_dict)

    # 5. Case pertains to (search strictly hash letter via R/O pattern)
    ro_data = extract_ro_pattern(hash_text)
    if ro_data:
        fields["pertains_service_no"] = ro_data["pertains_service_no"]
        fields["pertains_name"] = ro_data["pertains_name"]
        fields["pertains_unit"] = ro_data["pertains_unit"]
    else:
        fields["pertains_service_no"] = None
        fields["pertains_name"] = None
        fields["pertains_unit"] = None

    # 6. Dates
    fields["date_deposition"] = extract_deposition_date(hash_text)

    # Find return document
    return_doc_text = ""
    for fname, txt in files_dict.items():
        if "return" in fname and ("artefact" in fname or "artifact" in fname):
            return_doc_text = txt
            break

    fields["date_issuance"] = extract_issuance_date(return_doc_text)
    fields["date_intimation"] = extract_intimation_date(return_doc_text)
    fields["date_return"] = None

    return fields


# ── Field Count Helper ────────────────────────────────────────────────────────

def count_extracted_fields(fields: dict) -> int:
    """Count how many fields were successfully extracted (not None)."""
    extractable_fields = [
        "pertains_service_no", "pertains_name", "pertains_unit",
        "analyst", "investigating_officer",
        "date_deposition", "date_issuance", "date_intimation"
    ]
    return sum(1 for k in extractable_fields if fields.get(k) is not None)


# ── Year Extraction Helper ────────────────────────────────────────────────────

def extract_case_year(source_folder=None, case_name=None, date_deposition=None, created_at=None) -> str:
    """Extract 4-digit year from case metadata. Used to populate the year column."""
    if source_folder:
        m = re.search(r"[\/\\](20\d\d|19\d\d)[\/\\]", source_folder)
        if m:
            return m.group(1)
    if case_name:
        m = re.search(r"\b(20\d\d|19\d\d)\b", case_name)
        if m:
            return m.group(1)
    if date_deposition:
        m = re.search(r"\b(20\d\d|19\d\d)\b", date_deposition)
        if m:
            return m.group(1)
    if created_at:
        return str(created_at.year)
    return "Unknown"