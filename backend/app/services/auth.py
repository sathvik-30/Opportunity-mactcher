"""
services/auth.py — Phase 2.4
CHANGED: users_db dict replaced with SQLite DB functions.
UNCHANGED: hash_password, verify_password, create_token, decode_token
Phase 5 addition: get_current_user — a FastAPI dependency that resolves
the authenticated user from the Authorization header. It reuses
decode_token (no second JWT implementation) and is the single source
of "who is logged in" for any route that needs it.
"""

from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS
from app.database.connection import get_db

# Password hashing — UNCHANGED
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

# JWT — UNCHANGED
def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

# ── NEW: DB functions replacing users_db dict ─────────────────────

def get_user_by_email(db: Session, email: str):
    """REPLACES: users_db.get(email) — now queries SQLite."""
    from app.database.models import UserTable
    return db.query(UserTable).filter(UserTable.email == email).first()


def create_user(db: Session, user_data: dict):
    """REPLACES: users_db[email] = {...} — now inserts into SQLite."""
    import json
    from app.database.models import UserTable

    skills = user_data.get("skills", [])
    if isinstance(skills, list):
        skills_json = json.dumps(skills)
    else:
        skills_json = json.dumps([s.strip() for s in skills.split(",") if s.strip()])

    db_user = UserTable(
        id       = user_data["id"],
        name     = user_data["name"],
        email    = user_data["email"],
        password = user_data["password"],
        branch   = user_data["branch"],
        year     = int(user_data["year"]),
        skills   = skills_json,
        cgpa     = user_data.get("cgpa"),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def user_to_dict(user) -> dict:
    """Convert ORM UserTable object → dict with same shape as old users_db values."""
    import json
    skills = user.skills
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except Exception:
            skills = [s.strip() for s in skills.split(",") if s.strip()]
    return {
        "id":     user.id,
        "name":   user.name,
        "email":  user.email,
        "branch": user.branch,
        "year":   user.year,
        "skills": skills,
        "cgpa":   user.cgpa,
        # Phase 7: exposed so the frontend can initialize the email toggle
        # without a separate request.
        "email_notifications": bool(getattr(user, "email_notifications", 1)),
        # Phase 8: lets the frontend conditionally show the Admin nav item.
        # Backend routes NEVER trust this — every /admin/* route re-checks
        # is_admin server-side via require_admin.
        "is_admin": bool(getattr(user, "is_admin", 0)),
    }


# ── NEW (Phase 5): get_current_user — resolves the authenticated user ──
# Reuses decode_token above. No second JWT implementation, no manual
# decoding elsewhere. Any route can now do:
#     current_user: UserTable = Depends(get_current_user)
# and trust current_user.id — never trust a user_id sent by the client.

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency. Reads the 'Authorization: Bearer <token>' header,
    decodes it with the existing decode_token(), and loads the matching
    UserTable row from the database.

    Usage in a route:
        current_user: UserTable = Depends(get_current_user)

    Raises 401 if the header is missing, malformed, the token is
    invalid/expired, or the user no longer exists. Never trusts a
    user_id supplied by the client — identity always comes from the
    verified JWT payload.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    from app.database.models import UserTable
    user = db.query(UserTable).filter(UserTable.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# ── NEW (Phase 8): require_admin — admin-only route guard ──────────
# Layers on top of get_current_user (no second auth system). Any route
# using this dependency gets: valid JWT required (401 if not) AND
# admin role required (403 if not admin). This is real backend
# enforcement — frontend route hiding is never sufficient on its own.

def require_admin(current_user=Depends(get_current_user)):
    """
    FastAPI dependency for admin-only endpoints.
    Usage: current_admin = Depends(require_admin)
    Raises 403 if the authenticated user is not an admin.
    """
    if not getattr(current_user, "is_admin", 0):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
