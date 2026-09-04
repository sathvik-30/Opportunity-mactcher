
from pydantic import BaseModel


class Student(BaseModel):
    id: str | None = None
    name: str
    email: str
    college: str
    branch: str
    year: int                  # 1, 2, 3, 4
    skills: list[str]          # ["Python", "React", "ML"]
    interests: list[str]       # ["hackathon", "internship"]
    cgpa: float | None = None