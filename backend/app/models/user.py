from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    # min_length=6 matches the frontend's existing "Min 6 characters" hint
    # (Register.jsx) — server now actually enforces what the UI promises.
    password: str = Field(min_length=6)
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