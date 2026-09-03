from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class OpportunityType(str, Enum):
    internship = "internship"
    hackathon = "hackathon"
    scholarship = "scholarship"
    research = "research"

class Opportunity(BaseModel):
    id: Optional[str] = None
    title: str
    organization: str
    type: OpportunityType
    description: str
    required_skills: List[str]
    eligibility: dict          # e.g. {"min_year": 2, "branches": ["CS", "IT"]}
    deadline: str              # "2025-07-01"
    location: Optional[str] = None
    stipend: Optional[str] = None
    link: str