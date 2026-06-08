from pydantic import BaseModel
from typing import List, Optional

class Student(BaseModel):
    id: Optional[str] = None
    name: str
    email: str
    college: str
    branch: str
    year: int                  # 1, 2, 3, 4
    skills: List[str]          # ["Python", "React", "ML"]
    interests: List[str]       # ["hackathon", "internship"]
    cgpa: Optional[float] = None