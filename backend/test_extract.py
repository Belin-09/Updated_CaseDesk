import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from extractor.field_parser import parse_fields, count_extracted_fields
from validator import validate_extraction

# ── Test 1: Good document ─────────────────────────────────────────────────────
print("=== Test 1: Good document ===")
text1 = """
INVESTIGATOR NAME: Rahul Sharma
DATE: 10/06/2026
LOCATION: Connaught Place, New Delhi
INCIDENT TYPE: Theft
COMPLAINANT: Arvind Mehta
SUSPECT: Unknown
EVIDENCE: Mobile phone, Wallet
NOTES: Victim reported theft at a busy market area
"""
fields1 = parse_fields(text1)
flag1, reason1 = validate_extraction(text1, fields1)
print(f"Fields extracted : {count_extracted_fields(fields1)}/8")
print(f"Error flag       : {flag1}")
print(f"Error reason     : {reason1}")

# ── Test 2: Empty text ────────────────────────────────────────────────────────
print("\n=== Test 2: Empty text ===")
fields2 = parse_fields("")
flag2, reason2 = validate_extraction("", fields2)
print(f"Error flag       : {flag2}")
print(f"Error reason     : {reason2}")

# ── Test 3: Low fields ────────────────────────────────────────────────────────
print("\n=== Test 3: Low fields ===")
text3 = "This is a scanned document with no structured data at all."
fields3 = parse_fields(text3)
flag3, reason3 = validate_extraction(text3, fields3)
print(f"Fields extracted : {count_extracted_fields(fields3)}/8")
print(f"Error flag       : {flag3}")
print(f"Error reason     : {reason3}")

# ── Test 4: Low OCR confidence ────────────────────────────────────────────────
print("\n=== Test 4: Low OCR confidence ===")
fields4 = parse_fields(text1)
flag4, reason4 = validate_extraction(text1, fields4, ocr_confidence=45.0)
print(f"Error flag       : {flag4}")
print(f"Error reason     : {reason4}")

# ── Test 5: Extraction exception ──────────────────────────────────────────────
print("\n=== Test 5: Extraction exception ===")
fields5 = {}
flag5, reason5 = validate_extraction("", fields5, extraction_exception="pdfplumber crashed")
print(f"Error flag       : {flag5}")
print(f"Error reason     : {reason5}")