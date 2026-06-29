from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from database import get_db
from models import Case
from auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary")
def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # ── Top-level counts ─────────────────────────────────────────────────
    total_cases = db.query(func.count(Case.id)).scalar()
    open_cases = db.query(func.count(Case.id)).filter(Case.status == "open").scalar()
    closed_cases = db.query(func.count(Case.id)).filter(Case.status == "closed").scalar()
    pending_cases = db.query(func.count(Case.id)).filter(Case.status == "pending").scalar()
    flagged_cases = db.query(func.count(Case.id)).filter(Case.error_flag == True).scalar()

    # ── Cases by month (based on created_at) ────────────────────────────
    monthly_raw = (
        db.query(
            extract("year", Case.created_at).label("year"),
            extract("month", Case.created_at).label("month"),
            func.count(Case.id).label("count")
        )
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )
    month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    cases_by_month = [
        {"label": f"{month_names[int(m)]} {int(y)}", "count": c}
        for y, m, c in monthly_raw
    ]

    # ── Cases by incident type ──────────────────────────────────────────
    incident_raw = (
        db.query(Case.incident_type, func.count(Case.id))
        .filter(Case.incident_type.isnot(None))
        .group_by(Case.incident_type)
        .order_by(func.count(Case.id).desc())
        .all()
    )
    cases_by_incident_type = [
        {"label": label, "count": count} for label, count in incident_raw
    ]

    # ── Cases by officer ─────────────────────────────────────────────────
    officer_raw = (
        db.query(Case.officer, func.count(Case.id))
        .filter(Case.officer.isnot(None))
        .group_by(Case.officer)
        .order_by(func.count(Case.id).desc())
        .limit(10)
        .all()
    )
    cases_by_officer = [
        {"label": label, "count": count} for label, count in officer_raw
    ]

    # ── Review queue stats — breakdown by error reason ──────────────────
    reason_raw = (
        db.query(Case.error_reason, func.count(Case.id))
        .filter(Case.error_flag == True)
        .group_by(Case.error_reason)
        .all()
    )
    review_by_reason = [
        {"label": label or "Unknown", "count": count} for label, count in reason_raw
    ]

    resolved_count = (
        db.query(func.count(Case.id))
        .filter(Case.reviewed_by.isnot(None))
        .scalar()
    )

    return {
        "summary": {
            "total_cases": total_cases,
            "open_cases": open_cases,
            "closed_cases": closed_cases,
            "pending_cases": pending_cases,
            "flagged_cases": flagged_cases,
            "resolved_count": resolved_count,
        },
        "cases_by_month": cases_by_month,
        "cases_by_incident_type": cases_by_incident_type,
        "cases_by_officer": cases_by_officer,
        "review_by_reason": review_by_reason,
    }