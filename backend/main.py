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

@app.on_event("startup")
def startup_db_init():
    # 1. Ensure must_change_password column exists (auto-migration for existing DBs)
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0"))
            conn.commit()
    except Exception:
        # Column already exists or table doesn't support ALTER in this syntax
        pass

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