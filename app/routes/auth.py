from fastapi import APIRouter, HTTPException
from app.models.user import UserRegister, UserLogin
from app.services.auth import hash_password, verify_password, create_token, users_db
import uuid

router = APIRouter()

@router.post("/register")
def register(user: UserRegister):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    users_db[user.email] = {
        "id": user_id,
        "name": user.name,
        "email": user.email,
        "password": hash_password(user.password),
        "branch": user.branch,
        "year": user.year,
        "skills": [s.strip() for s in user.skills.split(",")],
        "cgpa": user.cgpa
    }
    
    token = create_token({"email": user.email, "id": user_id})
    return {"token": token, "user": {**users_db[user.email], "password": None}}

@router.post("/login")
def login(data: UserLogin):
    user = users_db.get(data.email)
    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_token({"email": user["email"], "id": user["id"]})
    return {"token": token, "user": {**user, "password": None}}