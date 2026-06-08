from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import json, os

from app.services.matcher import match_student_to_opportunities

router = APIRouter()

class StudentInput(BaseModel):
    name: str
    branch: str
    year: int
    skills: List[str]
    cgpa: Optional[float] = None

def load_opportunities():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(base_dir, "../../data/sample_opportunities.json"))
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@router.post("/match")
def get_matches(student: StudentInput):
    opportunities = load_opportunities()
    results = match_student_to_opportunities(student.dict(), opportunities)
    return {
        "student": student.name,
        "total_matches": len(results),
        "results": results
    }