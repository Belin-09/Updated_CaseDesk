from fastapi import FastAPI
from database import engine, Base, SessionLocal
from sqlalchemy import text
import models
from models import User
from auth import hash_password, verify_password
from routers import auth as auth_router
from routers import upload as upload_router

from routers import cases as cases_router

from routers import review as review_router

from fastapi.middleware.cors import CORSMiddleware

from routers import analytics as analytics_router

from routers import export as export_router



import os
from dotenv import load_dotenv
from fastapi import Request

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CaseDesk API", version="1.0")

def backfill_pertains_fields():
    db = SessionLocal()
    try:
        # Fetch all cases where pertains/analyst fields are NULL
        cases = db.query(models.Case).filter(
            (models.Case.pertains_service_no == None) |
            (models.Case.pertains_name == None) |
            (models.Case.pertains_unit == None) |
            (models.Case.analyst == None) |
            (models.Case.date_deposition == None)
        ).all()
        
        if not cases:
            return
            
        print(f"Starting automatic database backfill for {len(cases)} cases...")
        from extractor.field_parser import parse_fields
        
        for case in cases:
            # Reconstruct text from files or raw_text
            files = db.query(models.CaseFile).filter(models.CaseFile.case_id == case.id).all()
            if files:
                merged_parts = []
                for f in files:
                    if f.raw_text:
                        merged_parts.append(f"--- {f.file_name} ---\n{f.raw_text}")
                merged_text = "\n\n".join(merged_parts)
            else:
                merged_text = case.raw_text or ""
                
            if merged_text.strip():
                fields = parse_fields(merged_text)
                if not case.pertains_service_no:
                    case.pertains_service_no = fields.get("pertains_service_no")
                if not case.pertains_name:
                    case.pertains_name = fields.get("pertains_name")
                if not case.pertains_unit:
                    case.pertains_unit = fields.get("pertains_unit")
                if not case.analyst:
                    case.analyst = fields.get("analyst")
                if not case.investigating_officer:
                    case.investigating_officer = fields.get("investigating_officer")
                if not case.date_deposition:
                    case.date_deposition = fields.get("date_deposition")
                if not case.date_issuance:
                    case.date_issuance = fields.get("date_issuance")
                if not case.date_intimation:
                    case.date_intimation = fields.get("date_intimation")
                if not case.date_return:
                    case.date_return = fields.get("date_return")
                
                # Also update analytics columns if empty
                if not case.command:
                    case.command = fields.get("command")
                if not case.suspected_pio_numbers:
                    case.suspected_pio_numbers = fields.get("suspected_pio_numbers")
                    case.suspected_pio_count = fields.get("suspected_pio_count", 0)
                
        db.commit()
        print("Automatic database backfill completed successfully!")
    except Exception as e:
        print(f"Error running automatic backfill migration: {e}")
    finally:
        db.close()

def backfill_year_column():
    db = SessionLocal()
    try:
        from extractor.field_parser import extract_case_year
        cases = db.query(models.Case).filter(models.Case.year == None).all()
        if not cases:
            return
        print(f"Backfilling year column for {len(cases)} cases...")
        for case in cases:
            case.year = extract_case_year(
                source_folder=case.source_folder,
                case_name=case.case_name,
                date_deposition=case.date_deposition,
                created_at=case.created_at
            )
        db.commit()
        print("Year column backfill completed!")
    except Exception as e:
        print(f"Error backfilling year column: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_db_init():
    # 1. Auto-migration for users table
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0"))
            conn.commit()
    except Exception:
        pass

    # 2. Auto-migration for cases table
    migrations = [
        "ALTER TABLE cases ADD COLUMN command VARCHAR(100) NULL",
        "ALTER TABLE cases ADD COLUMN suspected_pio_numbers TEXT NULL",
        "ALTER TABLE cases ADD COLUMN suspected_pio_count INT DEFAULT 0",
        "ALTER TABLE cases ADD COLUMN analyst VARCHAR(255) NULL",
        "ALTER TABLE cases ADD COLUMN investigating_officer VARCHAR(255) NULL",
        "ALTER TABLE cases ADD COLUMN pertains_service_no VARCHAR(255) NULL",
        "ALTER TABLE cases ADD COLUMN pertains_name VARCHAR(255) NULL",
        "ALTER TABLE cases ADD COLUMN pertains_unit VARCHAR(255) NULL",
        "ALTER TABLE cases ADD COLUMN date_deposition VARCHAR(100) NULL",
        "ALTER TABLE cases ADD COLUMN date_issuance VARCHAR(100) NULL",
        "ALTER TABLE cases ADD COLUMN date_intimation VARCHAR(100) NULL",
        "ALTER TABLE cases ADD COLUMN date_return VARCHAR(100) NULL",
        "ALTER TABLE cases MODIFY file_name TEXT NULL",
        "ALTER TABLE cases DROP INDEX ft_cases_search",
        "ALTER TABLE cases MODIFY ocr_confidence FLOAT NULL",
        "ALTER TABLE cases ADD FULLTEXT INDEX ft_cases_search(file_name, file_path, incident_type, raw_text, status, error_reason, review_note, reviewed_by, uploaded_by, case_name, source_folder, command, suspected_pio_numbers, analyst, investigating_officer, pertains_service_no, pertains_name, pertains_unit, date_deposition, date_issuance, date_intimation, date_return)",
        "ALTER TABLE case_files ADD CONSTRAINT fk_casefile_case FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE",
        "ALTER TABLE cases ADD COLUMN year VARCHAR(10) NULL",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column already exists

    # 2. Create default admin if missing, or mark must_change_password=True if password is still 'admin'
    db = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.username == "admin").first()
        if not admin_exists:
            new_admin = User(
                username="admin",
                hashed_password=hash_password("admin"),
                role="admin",
                must_change_password=True
            )
            db.add(new_admin)
            db.commit()
            print("==================================================")
            print("Default admin account created automatically:")
            print("Username: admin  |  Password: admin")
            print("==================================================")
        else:
            if verify_password("admin", admin_exists.hashed_password):
                admin_exists.must_change_password = True
                db.commit()
                print("Default admin user detected with default password. Flagged must_change_password=True.")
    except Exception as e:
        print(f"Error seeding default admin: {e}")
    finally:
        db.close()

    try:
        backfill_pertains_fields()
    except Exception as e:
        print(f"Error running pertains fields backfill: {e}")

    # Backfill year column for existing cases
    try:
        backfill_year_column()
    except Exception as e:
        print(f"Error running year column backfill: {e}")

# Parse allowed origins from env
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000")
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 http://127.0.0.1:5500 http://localhost:5500 ws: wss:; "
        "frame-src 'self' http://127.0.0.1:8000 http://localhost:8000 http://127.0.0.1:5500 http://localhost:5500; "
        "frame-ancestors 'self' http://127.0.0.1:5500 http://localhost:5500 http://127.0.0.1:8000 http://localhost:8000; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self' data:;"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

app.include_router(cases_router.router)
app.include_router(auth_router.router)
app.include_router(upload_router.router)
app.include_router(review_router.router)
app.include_router(analytics_router.router)
app.include_router(export_router.router)



@app.get("/")
def root():
    return {"message": "CaseDesk API is running"}

@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}