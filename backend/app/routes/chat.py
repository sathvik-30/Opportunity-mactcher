"""
backend/app/routes/chat.py
─────────────────────────────────────────────────────────────────
POST /chat/advisor

Server-side proxy for the AI Career Advisor chatbot. The Groq API
key (config.GROQ_API_KEY) is used here only — it never reaches the
browser. Requires a valid JWT (get_current_user) so the backend's
Groq quota can't be spent by unauthenticated requests; this mirrors
how every other user-facing route in the app is protected.
─────────────────────────────────────────────────────────────────
"""

import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import GROQ_API_KEY
from app.database.models import UserTable
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    text: str


class OpportunitySummary(BaseModel):
    title: str
    organization: str
    type: str
    required_skills: List[str] = []


class AdvisorChatRequest(BaseModel):
    messages: List[ChatMessage]
    opportunities: List[OpportunitySummary] = []


def _build_system_prompt(student: UserTable, opportunities: List[OpportunitySummary]) -> str:
    """Same prompt shape the frontend used to build client-side — behavior-preserving."""
    import json

    skills = student.skills
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except Exception:
            skills = [s.strip() for s in skills.split(",") if s.strip()]
    skills_str = ", ".join(skills or [])

    opps_str = " | ".join(
        f"{o.title} by {o.organization} ({o.type}) skills:{','.join(o.required_skills)}"
        for o in opportunities[:8]
    )

    return (
        "You are a helpful career advisor for students. Be concise, friendly, specific.\n"
        f"Student: {student.name}, {student.branch} Year {student.year}, "
        f"Skills: {skills_str}, CGPA: {student.cgpa or 'N/A'}\n"
        f"Opportunities: {opps_str}\n"
        "Rules: Keep responses under 150 words unless writing a cover letter. "
        "Be encouraging and specific."
    )


@router.post("/advisor")
async def chat_advisor(
    body: AdvisorChatRequest,
    current_user: UserTable = Depends(get_current_user),
):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="AI advisor is not configured")
    if not body.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    system_prompt = _build_system_prompt(current_user, body.opportunities)
    groq_messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m.role, "content": m.text} for m in body.messages
    ]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GROQ_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                },
                json={
                    "model": GROQ_MODEL,
                    "max_tokens": 400,
                    "messages": groq_messages,
                },
            )
    except httpx.RequestError as e:
        logger.error(f"[chat] Groq request failed: {e}")
        raise HTTPException(status_code=502, detail="Could not reach AI advisor")

    if response.status_code != 200:
        logger.error(f"[chat] Groq returned {response.status_code}: {response.text[:300]}")
        raise HTTPException(status_code=502, detail="AI advisor request failed")

    data = response.json()
    try:
        reply = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        logger.error(f"[chat] Unexpected Groq response shape: {str(data)[:300]}")
        raise HTTPException(status_code=502, detail="AI advisor returned an unexpected response")

    return {"reply": reply}
