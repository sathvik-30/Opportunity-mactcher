"""
routes/auth.py — Phase 2.4
CHANGED: uses DB session via Depends(get_db) instead of users_db dict.
API CONTRACT: IDENTICAL — same request/response shapes, same status codes.
Frontend sees zero difference.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import UserLogin, UserRegister
from app.rate_limit import limiter
from app.services.auth import (
    create_token,
    create_user,
    get_current_user,
    get_user_by_email,
    hash_password,
    user_to_dict,
    verify_password,
)

router = APIRouter()


@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, user: UserRegister, db: Session = Depends(get_db)):
    # Check duplicate email (was: if user.email in users_db)
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id    = str(uuid.uuid4())
    skills_list = [s.strip() for s in user.skills.split(",") if s.strip()]

    db_user = create_user(db, {
        "id":       user_id,
        "name":     user.name,
        "email":    user.email,
        "password": hash_password(user.password),
        "branch":   user.branch,
        "year":     user.year,
        "skills":   skills_list,
        "cgpa":     user.cgpa,
    })

    token    = create_token({"email": db_user.email, "id": db_user.id})
    return {"token": token, "user": user_to_dict(db_user)}


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, data: UserLogin, db: Session = Depends(get_db)):
    # Find user (was: users_db.get(data.email))
    user = get_user_by_email(db, data.email)

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token({"email": user.email, "id": user.id})
    return {"token": token, "user": user_to_dict(user)}


@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    """
    Returns the authenticated user's profile for a still-valid stored
    token. Lets the frontend restore a session on page load instead of
    forcing a re-login every time despite the JWT still being valid.
    """
    return {"user": user_to_dict(current_user)}
