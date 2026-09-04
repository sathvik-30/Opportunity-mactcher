"""
backend/app/main.py
─────────────────────────────────────────────────────────────────
Phase 3 changes:
  1. Replaced @app.on_event("startup") with modern lifespan context
     manager — cleaner startup/shutdown, no deprecation warnings.
  2. Added scheduler start/stop inside lifespan.
  3. Registered /admin routes.

All existing routes, middleware, and cache logic unchanged.
─────────────────────────────────────────────────────────────────
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import CACHE_MINUTES, FRONTEND_URL
from app.rate_limit import limiter
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.matching import router as match_router
from app.routes.notifications import router as notifications_router
from app.routes.saved import router as saved_router
from app.routes.users import router as users_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_cached_opps = []
_cache_time  = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Replaces the deprecated @app.on_event("startup") / ("shutdown").

    On startup:
      1. Initialize database tables and seed sample data
      2. Start APScheduler background jobs

    On shutdown:
      1. Gracefully stop APScheduler (waits for running jobs)
    """
    # ── Startup ───────────────────────────────────────────────────
    logger.info("[main] Application starting...")

    # 1. Database
    from app.database.migrations import run_migrations
    run_migrations()

    # 2. Scheduler
    from app.scheduler.runner import start as start_scheduler
    start_scheduler()

    logger.info("[main] Application ready")
    yield

    # ── Shutdown ──────────────────────────────────────────────────
    logger.info("[main] Application shutting down...")
    from app.scheduler.runner import stop as stop_scheduler
    stop_scheduler()
    logger.info("[main] Shutdown complete")


app = FastAPI(
    title="Opportunity Matcher API",
    version="2.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "running", "message": "Opportunity Matcher API", "version": "2.0"}


@app.get("/opportunities")
async def get_opportunities(refresh: bool = False):
    """
    Returns all active opportunities from SQLite.
    Refreshes cache from DB every CACHE_MINUTES.
    When refresh=true, re-fetches from DB immediately.
    The scheduler keeps the DB updated automatically — no manual
    scraping needed.
    """
    global _cached_opps, _cache_time

    cache_expired = (
        _cache_time is None or
        datetime.now() - _cache_time > timedelta(minutes=CACHE_MINUTES)
    )

    if refresh or not _cached_opps or cache_expired:
        # Read from SQLite (populated by scheduler in background)
        from app.database.connection import SessionLocal
        from app.database.models import OpportunityTable
        db = SessionLocal()
        try:
            rows = (
                db.query(OpportunityTable)
                .filter(OpportunityTable.is_active == 1)
                .order_by(OpportunityTable.created_at.desc())
                .limit(500)
                .all()
            )
            _cached_opps = [row.to_dict() for row in rows]
            _cache_time  = datetime.now()
            logger.info(f"[main] Cache refreshed — {len(_cached_opps)} opportunities")
        finally:
            db.close()

    return {
        "count":        len(_cached_opps),
        "opportunities": _cached_opps,
        "last_updated": _cache_time.isoformat() if _cache_time else None,
    }


app.include_router(auth_router)
app.include_router(match_router)
app.include_router(admin_router)
app.include_router(saved_router)
app.include_router(notifications_router)
app.include_router(users_router)
app.include_router(chat_router)
