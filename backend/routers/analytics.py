import re
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Case
from auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


from sqlalchemy import func


@router.get("/summary")
def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # 1. Summary stats via aggregations
    status_counts = db.query(Case.status, func.count(Case.id)).group_by(Case.status).all()
    
    total_cases = 0
    open_cases = 0
    closed_cases = 0
    pending_cases = 0
    
    for status, count in status_counts:
        total_cases += count
        if status == "open":
            open_cases += count
        elif status == "closed":
            closed_cases += count
        elif status == "pending":
            pending_cases += count

    flagged_cases = db.query(func.count(Case.id)).filter(Case.error_flag == True).scalar() or 0
    total_pio_numbers = int(db.query(func.sum(Case.suspected_pio_count)).scalar() or 0)

    # 2. Cases per Year
    year_counts = defaultdict(int)
    yr_counts_db = db.query(Case.year, func.count(Case.id)).group_by(Case.year).all()
    for yr, count in yr_counts_db:
        year_counts[yr or "Unknown"] += count

    # 3. Cases per Command per Year
    year_command = defaultdict(lambda: defaultdict(int))
    cmd_yr_counts = db.query(Case.year, Case.command, func.count(Case.id)).group_by(Case.year, Case.command).all()
    for yr, cmd, count in cmd_yr_counts:
        year_command[yr or "Unknown"][cmd or "Unassigned"] += count

    # 4. Cases per Type per Year
    year_type = defaultdict(lambda: defaultdict(int))
    type_yr_counts = db.query(Case.year, Case.incident_type, func.count(Case.id)).group_by(Case.year, Case.incident_type).all()
    case_types = ["Int (Cyber Espionage)", "Int (Social Media violation)", "DV / Misc"]
    
    for yr, ctype, count in type_yr_counts:
        mapped_type = ctype if ctype in case_types else "DV / Misc"
        year_type[yr or "Unknown"][mapped_type] += count

    # 5. PIO numbers frequency per Year
    # Load only necessary string columns to avoid high memory usage
    year_pio_freq = defaultdict(lambda: defaultdict(int))
    pio_cases = db.query(Case.year, Case.suspected_pio_numbers).filter(Case.suspected_pio_numbers.isnot(None)).all()
    
    for yr, pio_str in pio_cases:
        y = yr or "Unknown"
        if pio_str:
            nums = [n.strip() for n in pio_str.split(",") if n.strip()]
            for n in nums:
                year_pio_freq[y][n] += 1

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

    commands = ["Central", "Northern", "Southern", "Eastern", "Western", "North Eastern", "South Western"]
    
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
    # Load only necessary string columns
    pio_cases = db.query(Case.id, Case.case_name, Case.file_name, Case.suspected_pio_numbers)\
                  .filter(Case.year == year)\
                  .filter(Case.suspected_pio_numbers.isnot(None))\
                  .all()
                  
    pio_map = defaultdict(list)
    
    for c_id, case_name, file_name, pio_str in pio_cases:
        if pio_str:
            numbers = [num.strip() for num in pio_str.split(",") if num.strip()]
            for num in numbers:
                pio_map[num].append({
                    "case_id": c_id,
                    "case_name": case_name or file_name or f"Case #{c_id}"
                })
                
    results = []
    for num, cases in pio_map.items():
        results.append({
            "number": num,
            "occurrences": len(cases),
            "case_id": cases[0]["case_id"]
        })
        
    results.sort(key=lambda x: (-x["occurrences"], x["number"]))
    return {"year": year, "numbers": results}