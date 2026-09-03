"""
backend/app/routes/saved.py — Phase 5
─────────────────────────────────────────────────────────────────
Persistent saved opportunities.

Reuses, does NOT duplicate:
  - SavedOpportunityTable (already existed in database/models.py,
    already has the user_id+opportunity_id UniqueConstraint)
  - OpportunityTable + its to_dict() (same shape /opportunities uses)
  - get_current_user (Phase 5 addition to services/auth.py) — the
    only source of "who is logged in"; user_id is NEVER trusted from
    the request body
  - get_db (existing SQLAlchemy session dependency)

Endpoints:
  POST   /saved                  — save an opportunity for the current user
  GET    /saved                  — list the current user's saved opportunities
  DELETE /saved/{opportunity_id} — unsave
─────────────────────────────────────────────────────────────────
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.connection import get_db
from app.database.models import SavedOpportunityTable, OpportunityTable, UserTable
from app.services.auth import get_current_user

router = APIRouter()


class SaveRequest(BaseModel):
    opportunity_id: str


@router.post("/saved")
def save_opportunity(
    body: SaveRequest,
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    """
    Save an opportunity for the authenticated user.

    - 404 if the opportunity doesn't exist.
    - 409 if the user already saved it (no duplicate row is ever created —
      the DB-level UniqueConstraint on (user_id, opportunity_id) backs
      this up even under a race condition).
    """
    opportunity = (
        db.query(OpportunityTable)
        .filter(OpportunityTable.id == body.opportunity_id)
        .first()
    )
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    existing = (
        db.query(SavedOpportunityTable)
        .filter(
            SavedOpportunityTable.user_id == current_user.id,
            SavedOpportunityTable.opportunity_id == body.opportunity_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Opportunity already saved")

    record = SavedOpportunityTable(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        opportunity_id=body.opportunity_id,
    )

    try:
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save opportunity")

    return {
        "success": True,
        "message": "Opportunity saved",
        "opportunity_id": body.opportunity_id,
    }


@router.get("/saved")
def get_saved_opportunities(
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    """
    Return the authenticated user's saved opportunities, newest first,
    with full opportunity details (same shape as GET /opportunities'
    items) plus a savedAt timestamp. Only ever queries rows belonging
    to current_user.id — never trusts a user_id from the client.
    """
    rows = (
        db.query(SavedOpportunityTable)
        .filter(SavedOpportunityTable.user_id == current_user.id)
        .order_by(SavedOpportunityTable.saved_at.desc())
        .all()
    )

    saved = []
    for row in rows:
        opp = row.opportunity
        if not opp:
            # Opportunity was deleted from the catalog since being saved —
            # skip it rather than returning a broken/partial record.
            continue
        item = opp.to_dict()
        item["savedAt"] = row.saved_at.isoformat() if row.saved_at else None
        saved.append(item)

    return {"count": len(saved), "saved": saved}


@router.delete("/saved/{opportunity_id}")
def delete_saved_opportunity(
    opportunity_id: str,
    db: Session = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    """
    Remove a saved opportunity for the authenticated user.
    Only deletes a record that belongs to BOTH current_user.id AND
    the given opportunity_id — a user can never delete someone else's
    saved record. Returns a clean (non-crashing) response if there was
    nothing to delete.
    """
    record = (
        db.query(SavedOpportunityTable)
        .filter(
            SavedOpportunityTable.user_id == current_user.id,
            SavedOpportunityTable.opportunity_id == opportunity_id,
        )
        .first()
    )

    if not record:
        return {
            "success": False,
            "message": "Saved opportunity not found",
            "opportunity_id": opportunity_id,
        }

    try:
        db.delete(record)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not remove saved opportunity")

    return {
        "success": True,
        "message": "Opportunity removed from saved",
        "opportunity_id": opportunity_id,
    }
