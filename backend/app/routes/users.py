"""
backend/app/routes/users.py — Phase 7
─────────────────────────────────────────────────────────────────
PATCH /users/preferences
PATCH /users/profile

Lets the authenticated user update their own notification
preferences or profile fields. Both reuse get_current_user —
identity always comes from the verified JWT, never from the
request body. A user can only ever update their own row.
─────────────────────────────────────────────────────────────────
"""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.connection import get_db
from app.database.models import UserTable
from app.services.auth import get_current_user, user_to_dict

router = APIRouter()


class PreferencesUpdate(BaseModel):
    """All fields optional — only what's sent gets updated (PATCH semantics)."""
    email_notifications: Optional[bool] = None
    notify_internship:   Optional[bool] = None
    notify_job:          Optional[bool] = None
    notify_hackathon:    Optional[bool] = None
    notify_scholarship:  Optional[bool] = None
    notify_research:     Optional[bool] = None
    notify_remote_only:  Optional[bool] = None


@router.patch("/users/preferences")
def update_preferences(
    body: PreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    updates = body.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No preference fields provided")

    for field, value in updates.items():
        setattr(current_user, field, 1 if value else 0)

    try:
        db.commit()
        db.refresh(current_user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update preferences")

    return {"success": True, "user": user_to_dict(current_user)}


class ProfileUpdate(BaseModel):
    """All fields optional — only what's sent gets updated (PATCH semantics)."""
    name:   Optional[str] = None
    branch: Optional[str] = None
    year:   Optional[int] = None
    cgpa:   Optional[float] = None
    skills: Optional[List[str]] = None


@router.patch("/users/profile")
def update_profile(
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    """
    Update the authenticated user's own profile (name/branch/year/cgpa/
    skills). Previously the frontend "Save & Re-match" button only
    updated local React state and never called the backend — edits were
    silently lost on refresh or logout. This is the endpoint that fixes
    that; see Dashboard.jsx's saveProfile().
    """
    updates = body.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No profile fields provided")

    if "name" in updates and not updates["name"].strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    if "branch" in updates and not updates["branch"].strip():
        raise HTTPException(status_code=400, detail="Branch cannot be empty")

    if "skills" in updates:
        current_user.skills = json.dumps(updates.pop("skills"))
    for field, value in updates.items():
        setattr(current_user, field, value)

    try:
        db.commit()
        db.refresh(current_user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update profile")

    return {"success": True, "user": user_to_dict(current_user)}
