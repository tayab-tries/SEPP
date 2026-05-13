"""
server/routers/auth.py
Module 1 — Auth & Identity

Endpoints:
    POST /auth/register-with-face  — atomic: validate face THEN create account
    POST /auth/login               — returns JWT
    POST /auth/enroll-face         — re-enrollment only (post-registration)
    POST /auth/verify-face         — exam proctoring
    GET  /auth/me                  — current user profile
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from server.database import get_db
from server.config import get_settings
from server.models.models import User
from server.dependencies import get_current_user
from server.services.face_service import extract_embedding, verify_embedding
from shared.constants import Role

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Schemas ────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token:  str
    token_type:    str = "bearer"
    role:          Role
    user_id:       str
    full_name:     str
    face_enrolled: bool


# ── Helpers ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/register-with-face", status_code=201)
async def register_with_face(
    # Form fields
    email:       str        = Form(...),
    first_name:  str        = Form(...),
    last_name:   str        = Form(...),
    password:    str        = Form(...),
    role:        str        = Form(...),
    institution: str        = Form(""),
    department:  str        = Form(""),
    # Face image
    image:       UploadFile = File(...),
    db:          Session    = Depends(get_db),
):
    """
    Atomic registration + face enrollment.
    Face is validated BEFORE the account is created.
    If face detection fails → 422, no account created.
    If account is created but embedding save fails → account is deleted, 500 returned.
    """
    # 1. Check email uniqueness first (cheap check before GPU work)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered.")

    # 2. Extract face embedding BEFORE creating account
    contents = await image.read()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(contents)
        tmp_path = f.name

    try:
        embedding = extract_embedding(tmp_path)
    finally:
        os.unlink(tmp_path)

    if embedding is None:
        raise HTTPException(
            status_code=422,
            detail="No face detected. Please retake your photo with good lighting and a clear front-facing view.",
        )

    # 3. Create user
    try:
        role_enum = Role(role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid role: {role}")

    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        hashed_password=hash_password(password),
        role=role_enum,
        institution=institution or None,
        department=department or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 4. Save embedding — if this fails, roll back the account
    try:
        user.face_embedding = embedding
        user.face_enrolled  = True
        db.commit()
    except Exception:
        db.delete(user)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail="Account created but face enrollment failed. Please try registering again.",
        )

    token = create_access_token({"sub": user.id, "role": user.role})
    return {
        "user_id":      user.id,
        "access_token": token,
        "message":      "Registration successful.",
    }


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db:   Session = Depends(get_db),
):
    """Authenticate with email + password. Returns JWT."""
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenResponse(
        access_token=token,
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
        face_enrolled=user.face_enrolled,
    )


@router.post("/enroll-face")
async def enroll_face(
    image:        UploadFile = File(...),
    current_user: User       = Depends(get_current_user),
    db:           Session    = Depends(get_db),
):
    """Re-enrollment endpoint — not used in normal signup flow."""
    contents = await image.read()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(contents)
        tmp_path = f.name

    try:
        embedding = extract_embedding(tmp_path)
    finally:
        os.unlink(tmp_path)

    if embedding is None:
        raise HTTPException(
            status_code=422,
            detail="No face detected. Please try again with better lighting.",
        )

    current_user.face_embedding = embedding
    current_user.face_enrolled  = True
    db.commit()

    return {"message": "Face enrolled successfully.", "embedding_dims": len(embedding)}


@router.post("/verify-face")
async def verify_face(
    image:        UploadFile = File(...),
    current_user: User       = Depends(get_current_user),
    db:           Session    = Depends(get_db),
):
    """Compare live face against stored embedding. Used by camera monitor during exams."""
    if not current_user.face_enrolled or not current_user.face_embedding:
        raise HTTPException(status_code=400, detail="Face not enrolled.")

    contents = await image.read()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(contents)
        tmp_path = f.name

    try:
        result = verify_embedding(
            image_path=tmp_path,
            stored_embedding=list(current_user.face_embedding),
        )
    finally:
        os.unlink(tmp_path)

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return result


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the currently authenticated user's profile."""
    return {
        "user_id":      current_user.id,
        "email":        current_user.email,
        "first_name":   current_user.first_name,
        "last_name":    current_user.last_name,
        "full_name":    current_user.full_name,
        "role":         current_user.role,
        "institution":  current_user.institution,
        "department":   current_user.department,
        "face_enrolled": current_user.face_enrolled,
        "created_at":   current_user.created_at,
    }