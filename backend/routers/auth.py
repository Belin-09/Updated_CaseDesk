from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from models import User, AuditLog
from auth import hash_password, verify_password, create_access_token, get_current_user, require_role
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Auth"])


# --- Schemas (inline for now) ---

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "officer"  # default role


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str


# --- Register ---

@router.post("/register", status_code=201)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role("admin"))
):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    if payload.role not in ["admin", "officer", "viewer"]:
        raise HTTPException(
            status_code=400,
            detail="Role must be admin, officer, or viewer"
        )

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Audit log
    log = AuditLog(
        username=admin_user.username,
        action="REGISTERED_USER",
        case_id=None,
        details=f"Registered user '{payload.username}' with role '{payload.role}'"
    )
    db.add(log)
    db.commit()

    return {"message": f"User '{payload.username}' registered successfully", "role": payload.role}


# --- Create User (Admin Only) ---

@router.post("/create-user", status_code=201)
def create_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role("admin"))
):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    if payload.role not in ["admin", "officer", "viewer"]:
        raise HTTPException(
            status_code=400,
            detail="Role must be admin, officer, or viewer"
        )

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Audit log
    log = AuditLog(
        username=admin_user.username,
        action="CREATED_USER",
        case_id=None,
        details=f"Created user '{payload.username}' with role '{payload.role}'"
    )
    db.add(log)
    db.commit()

    return {"message": f"User '{payload.username}' created successfully", "role": payload.role}


# --- List Users (Admin Only) ---

@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role("admin"))
):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "created_at": u.created_at
        }
        for u in users
    ]


# --- Change Password ---

@router.put("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Incorrect current password"
        )

    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()

    # Audit log
    log = AuditLog(
        username=current_user.username,
        action="CHANGED_PASSWORD",
        case_id=None,
        details="User changed their password"
    )
    db.add(log)
    db.commit()

    return {"message": "Password changed successfully"}


# --- Login ---

@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    token = create_access_token(data={"sub": user.username, "role": user.role})

    # Audit log
    log = AuditLog(username=user.username, action="LOGIN", case_id=None)
    db.add(log)
    db.commit()

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role
    }


# --- Me (test protected route) ---

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "role": current_user.role
    }