from pydantic import BaseModel
from typing import Optional

class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    branch: str
    year: int
    skills: str        # comma separated
    cgpa: Optional[float] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: str
    name: str
    email: str
    branch: str
    year: int
    skills: list
    cgpa: Optional[float] = None