from enum import Enum

from pydantic import BaseModel


class OpportunityType(str, Enum):
    internship = "internship"
    hackathon = "hackathon"
    scholarship = "scholarship"
    research = "research"

class Opportunity(BaseModel):
    id: str | None = None
    title: str
    organization: str
    type: OpportunityType
    description: str
    required_skills: list[str]
    eligibility: dict          # e.g. {"min_year": 2, "branches": ["CS", "IT"]}
    deadline: str              # "2025-07-01"
    location: str | None = None
    stipend: str | None = None
    link: str