from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.matching import router as match_router  # add at top
import json
import os

app = FastAPI(title="Opportunity Matcher API", version="1.0")
app.include_router(match_router)  # add after middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_opportunities():
    # build absolute path regardless of where uvicorn is run from
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "..", "data", "sample_opportunities.json")
    path = os.path.normpath(path)
    
    print(f"Looking for file at: {path}")  # this will show in your terminal
    
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@app.get("/")
def health_check():
    return {"status": "running", "message": "Opportunity Matcher API 🎯"}

@app.get("/opportunities")
def get_opportunities():
    data = load_opportunities()
    return {"opportunities": data, "message": "Data loaded successfully"}