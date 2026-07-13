import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER
from datetime import datetime

from database import get_db
from models import Case, CaseFile, AuditLog
from auth import get_current_user

router = APIRouter(prefix="/export", tags=["PDF Export"])

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)


@router.get("/{case_id}")
def export_case_pdf(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    files = db.query(CaseFile).filter(CaseFile.case_id == case_id).all()

    file_name = f"case_{case_id}_report.pdf"
    file_path = os.path.join(EXPORT_DIR, file_name)

    _build_pdf(case, files, file_path)

    # Audit log
    log = AuditLog(
        username=current_user.username,
        action="EXPORTED_PDF",
        case_id=case.id,
        details=f"Exported PDF report for case {case_id}"
    )
    db.add(log)
    db.commit()

    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type="application/pdf"
    )


def _build_pdf(case: Case, files: list, file_path: str):
    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Heading1"],
        fontSize=18, alignment=TA_CENTER, spaceAfter=4,
        textColor=colors.HexColor("#1a2129")
    )
    subtitle_style = ParagraphStyle(
        "SubtitleStyle", parent=styles["Normal"],
        fontSize=10, alignment=TA_CENTER, textColor=colors.grey,
        spaceAfter=20
    )
    section_style = ParagraphStyle(
        "SectionStyle", parent=styles["Heading2"],
        fontSize=12, spaceBefore=16, spaceAfter=8,
        textColor=colors.HexColor("#2a3441")
    )
    body_style = ParagraphStyle(
        "BodyStyle", parent=styles["Normal"],
        fontSize=10, leading=14
    )

    elements = []

    # ── Header ───────────────────────────────────────────────────────────
    elements.append(Paragraph("CaseDesk — Case Report", title_style))
    elements.append(Paragraph(
        f"Generated on {datetime.now().strftime('%d %B %Y, %H:%M')}",
        subtitle_style
    ))

    status_color = {
        "open": colors.HexColor("#16a34a"),
        "closed": colors.grey,
        "pending": colors.HexColor("#ca8a04"),
    }.get(case.status, colors.black)

    # ── Case overview table ─────────────────────────────────────────────
    overview_data = [
        ["Case Name", case.case_name or "—", "Flagged", "Yes" if case.error_flag else "No"],
        ["Incident Type", case.incident_type or "—", "Uploaded By", case.uploaded_by or "—"],
    ]

    overview_table = Table(overview_data, colWidths=[80, 150, 80, 150])
    overview_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#334155")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#334155")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(overview_table)

    # ── Custom fields table ─────────────────────────────────────────────
    elements.append(Paragraph("Case Details", section_style))
    custom_data = [
        ["Analyst", case.analyst or "—", "Investigating Officer", case.investigating_officer or "—"],
        ["Pertains Service No", case.pertains_service_no or "—", "Pertains Name", case.pertains_name or "—"],
        ["Pertains Unit", case.pertains_unit or "—", "Military Command", case.command or "—"],
        ["Deposition Date", case.date_deposition or "—", "Hash Issuance Date", case.date_issuance or "—"],
        ["Intimation Date", case.date_intimation or "—", "Return Date", case.date_return or "—"],
    ]
    custom_table = Table(custom_data, colWidths=[110, 120, 110, 120])
    custom_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#334155")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#334155")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(custom_table)

    # ── Source files ─────────────────────────────────────────────────────
    elements.append(Paragraph("Source Files", section_style))
    if files:
        file_data = [["File Name", "Type", "OCR Confidence", "Status"]]
        for f in files:
            confidence = f"{f.ocr_confidence}%" if f.ocr_confidence is not None else "—"
            status = "Error" if f.extraction_error else "OK"
            file_data.append([f.file_name, f.file_type, confidence, status])

        file_table = Table(file_data, colWidths=[200, 80, 100, 80])
        
        style_cmds = [
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ]
        
        for i in range(1, len(file_data)):
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8fafc")))
                
        file_table.setStyle(TableStyle(style_cmds))
        elements.append(file_table)
    else:
        elements.append(Paragraph("No source files recorded.", body_style))

    # ── Review / audit info ─────────────────────────────────────────────
    elements.append(Paragraph("Review Status", section_style))
    review_data = [
        ["Error Flag", f"{'Yes — ' + case.error_reason if case.error_flag else 'No'}", "Review Note", case.review_note or "—"],
        ["Reviewed By", case.reviewed_by or "—", "Reviewed At", case.reviewed_at.strftime('%d %b %Y, %H:%M') if case.reviewed_at else "—"],
        ["Uploaded By", case.uploaded_by or "—", "Created At", case.created_at.strftime('%d %b %Y, %H:%M') if case.created_at else "—"],
    ]
    
    review_table = Table(review_data, colWidths=[100, 150, 90, 150])
    review_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#334155")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#334155")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(review_table)

    # ── Footer note ──────────────────────────────────────────────────────
    elements.append(Spacer(1, 20))
    footer_style = ParagraphStyle(
        "FooterStyle", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey, alignment=TA_CENTER
    )
    elements.append(Paragraph(
        "This report was generated automatically by CaseDesk. For official use only.",
        footer_style
    ))

    doc.build(elements)