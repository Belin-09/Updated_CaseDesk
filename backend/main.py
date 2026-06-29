from fastapi import FastAPI
from database import engine, Base, SessionLocal
from sqlalchemy import text
import models
from models import User
from auth import hash_password
from routers import auth as auth_router
from routers import upload as upload_router

from routers import cases as cases_router

from routers import review as review_router

from fastapi.middleware.cors import CORSMiddleware

from routers import analytics as analytics_router

from routers import export as export_router



Base.metadata.create_all(bind=engine)

app = FastAPI(title="CaseDesk API", version="1.0")

@app.on_event("startup")
def create_default_admin():
    db = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.username == "admin").first()
        if not admin_exists:
            new_admin = User(
                username="admin",
                hashed_password=hash_password("admin"),
                role="admin"
            )
            db.add(new_admin)
            db.commit()
            print("==================================================")
            print("Default admin account created automatically:")
            print("Username: admin  |  Password: admin")
            print("==================================================")
    except Exception as e:
        print(f"Error seeding default admin: {e}")
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this later for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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