import re
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Case
from auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def extract_year_from_case(c: Case) -> str:
    """Extract 4-digit year from source_folder, case_name, date, or created_at."""
    if c.source_folder:
        m = re.search(r"[\/\\](20\d\d|19\d\d)[\/\\]", c.source_folder)
        if m:
            return m.group(1)
    if c.case_name:
        m = re.search(r"\b(20\d\d|19\d\d)\b", c.case_name)
        if m:
            return m.group(1)
    if c.date:
        m = re.search(r"\b(20\d\d|19\d\d)\b", c.date)
        if m:
            return m.group(1)
    if c.created_at:
        return str(c.created_at.year)
    return "Unknown"


@router.get("/summary")
def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    all_cases = db.query(Case).all()

    total_cases = len(all_cases)
    open_cases = sum(1 for c in all_cases if c.status == "open")
    closed_cases = sum(1 for c in all_cases if c.status == "closed")
    pending_cases = sum(1 for c in all_cases if c.status == "pending")
    flagged_cases = sum(1 for c in all_cases if c.error_flag)
    total_pio_numbers = sum(getattr(c, "suspected_pio_count", 0) or 0 for c in all_cases)

    # 1. Cases per Year
    year_counts = defaultdict(int)
    # 2. PIO numbers frequency per Year
    year_pio_freq = defaultdict(lambda: defaultdict(int))
    # 3. Cases per Command per Year
    year_command = defaultdict(lambda: defaultdict(int))
    # 4. Cases per Type per Year
    year_type = defaultdict(lambda: defaultdict(int))

    commands = ["Central", "Northern", "Southern", "Eastern", "Western", "North Eastern", "South Western"]
    case_types = ["Int (Cyber Espionage)", "Int (Social Media violation)", "DV / Misc"]

    for c in all_cases:
        yr = extract_year_from_case(c)
        year_counts[yr] += 1

        pio_str = getattr(c, "suspected_pio_numbers", None)
        if pio_str:
            nums = [n.strip() for n in pio_str.split(",") if n.strip()]
            for n in nums:
                year_pio_freq[yr][n] += 1

        cmd = getattr(c, "command", None) or "Unassigned"
        year_command[yr][cmd] += 1

        ctype = c.incident_type or "DV / Misc"
        if ctype not in case_types:
            ctype = "DV / Misc"
        year_type[yr][ctype] += 1

    sorted_years = sorted([y for y in year_counts.keys() if y != "Unknown"], reverse=True)
    if "Unknown" in year_counts:
        sorted_years.append("Unknown")

    cases_per_year = [{"year": y, "count": year_counts[y]} for y in sorted_years]
    
    pio_per_year = []
    for y in sorted_years:
        freq = year_pio_freq.get(y, {})
        details = [{"number": num, "occurrences": count} for num, count in freq.items()]
        # Sort details by occurrences descending, then by number
        details.sort(key=lambda x: (-x["occurrences"], x["number"]))
        pio_per_year.append({
            "year": y,
            "count": len(freq),
            "details": details
        })

    cases_by_command_year = {
        "years": sorted_years,
        "commands": commands + ["Unassigned"],
        "data": {
            y: {cmd: year_command[y][cmd] for cmd in (commands + ["Unassigned"])}
            for y in sorted_years
        }
    }

    cases_by_type_year = {
        "years": sorted_years,
        "types": case_types,
        "data": {
            y: {t: year_type[y][t] for t in case_types}
            for y in sorted_years
        }
    }

    return {
        "summary": {
            "total_cases": total_cases,
            "open_cases": open_cases,
            "closed_cases": closed_cases,
            "pending_cases": pending_cases,
            "flagged_cases": flagged_cases,
            "total_pio_numbers": total_pio_numbers,
        },
        "cases_per_year": cases_per_year,
        "pio_per_year": pio_per_year,
        "cases_by_command_year": cases_by_command_year,
        "cases_by_type_year": cases_by_type_year,
    }


@router.get("/pio-numbers")
def get_pio_numbers_by_year(
    year: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    all_cases = db.query(Case).all()
    pio_map = defaultdict(list)
    
    for c in all_cases:
        yr = extract_year_from_case(c)
        if yr == year and c.suspected_pio_numbers:
            # Split and clean
            numbers = [num.strip() for num in c.suspected_pio_numbers.split(",") if num.strip()]
            for num in numbers:
                pio_map[num].append({
                    "case_id": c.id,
                    "case_name": c.case_name or c.file_name or f"Case #{c.id}"
                })
                
    results = []
    for num, cases in pio_map.items():
        results.append({
            "number": num,
            "occurrences": len(cases),
            "case_id": cases[0]["case_id"] # Provide a quick link to the first case
        })
        
    results.sort(key=lambda x: (-x["occurrences"], x["number"]))
    return {"year": year, "numbers": results}