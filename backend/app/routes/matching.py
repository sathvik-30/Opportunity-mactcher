"""
routes/matching.py — Phase 2.5
CHANGED: load_opportunities() reads from SQLite instead of JSON file.
UNCHANGED: StudentInput model, /match endpoint, TF-IDF matching logic.
Response format is byte-for-byte identical.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from app.services.matcher import match_student_to_opportunities
from app.database.connection import SessionLocal
from app.database.models import OpportunityTable

router = APIRouter()


class StudentInput(BaseModel):
    """UNCHANGED."""
    name:   str
    branch: str
    year:   int
    skills: List[str]
    cgpa:   Optional[float] = None


def load_opportunities() -> list:
    """
    OLD: reads data/sample_opportunities.json (3 static records)
    NEW: queries SQLite opportunities table WHERE is_active=1
    Returns same list-of-dicts structure — matcher is unchanged.
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(OpportunityTable)
            .filter(OpportunityTable.is_active == 1)
            .all()
        )
        return [row.to_dict() for row in rows]
    finally:
        db.close()


@router.post("/match")
def get_matches(student: StudentInput):
    """UNCHANGED endpoint. Same request, same response."""
    opportunities = load_opportunities()
    results = match_student_to_opportunities(student.dict(), opportunities)
    return {
        "student":       student.name,
        "total_matches": len(results),
        "results":       results,
    }
