from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.matching import router as match_router
from app.routes.auth import router as auth_router
import json, os

app = FastAPI(title="Opportunity Matcher API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_opportunities():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(base_dir, "..", "data", "sample_opportunities.json"))
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@app.get("/")
def health_check():
    return {"status": "running", "message": "Opportunity Matcher API 🎯"}

@app.get("/opportunities")
def get_opportunities():
    data = load_opportunities()
    return {"count": len(data), "opportunities": data}

app.include_router(auth_router)
app.include_router(match_router)