"""
backend/app/scheduler/runner.py
─────────────────────────────────────────────────────────────────
APScheduler setup and lifecycle management.

Uses BackgroundScheduler (runs in a daemon thread — compatible
with sync FastAPI / uvicorn --reload).

Key design decisions:
  - Stable job IDs + replace_existing=True prevent duplicates
    across uvicorn --reload cycles within the same process
  - max_instances=1 per job prevents overlapping runs
  - coalesce=True collapses missed executions into one catch-up run
  - Scheduler is stored in a module-level variable so the FastAPI
    lifespan can start/stop it cleanly
─────────────────────────────────────────────────────────────────
"""

import logging
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import pytz

logger = logging.getLogger(__name__)

# ── Module-level scheduler instance ──────────────────────────────
# Shared across the entire process. start()/stop() called by lifespan.
_scheduler: BackgroundScheduler | None = None


def _read_config() -> dict:
    """
    Read scheduler configuration from environment.
    Priority: SCRAPER_INTERVAL_MINUTES > SCRAPER_INTERVAL_HOURS
    This lets developers test with short intervals without changing code.
    """
    tz_name    = os.getenv("APP_TIMEZONE", "Asia/Kolkata")
    enabled    = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    on_startup = os.getenv("RUN_SCRAPER_ON_STARTUP", "false").lower() == "true"

    # Minutes takes priority over hours (for dev/testing)
    interval_minutes = os.getenv("SCRAPER_INTERVAL_MINUTES")
    interval_hours   = os.getenv("SCRAPER_INTERVAL_HOURS", "6")

    if interval_minutes:
        interval_seconds = int(interval_minutes) * 60
        interval_label   = f"every {interval_minutes} minute(s)"
    else:
        interval_seconds = int(interval_hours) * 3600
        interval_label   = f"every {interval_hours} hour(s)"

    return {
        "tz_name":          tz_name,
        "enabled":          enabled,
        "on_startup":       on_startup,
        "interval_seconds": interval_seconds,
        "interval_label":   interval_label,
    }


def _on_job_executed(event):
    logger.info(f"[scheduler] Job '{event.job_id}' completed")


def _on_job_error(event):
    logger.error(
        f"[scheduler] Job '{event.job_id}' raised an exception: "
        f"{event.exception}"
    )


def get_scheduler() -> BackgroundScheduler | None:
    """Return the current scheduler instance (may be None if disabled)."""
    return _scheduler


def start() -> None:
    """
    Initialize and start the BackgroundScheduler.
    Registers two jobs:
      - scrape_opportunities  (configurable interval, default 6h)
      - cleanup_expired_opps  (daily at 01:00 APP_TIMEZONE)

    Safe to call multiple times — checks _scheduler state first.
    """
    global _scheduler

    cfg = _read_config()

    if not cfg["enabled"]:
        logger.info("[scheduler] SCHEDULER_ENABLED=false — scheduler not started")
        return

    if _scheduler is not None and _scheduler.running:
        logger.info("[scheduler] Already running — skipping start")
        return

    try:
        tz = pytz.timezone(cfg["tz_name"])
    except Exception:
        logger.warning(f"[scheduler] Unknown timezone '{cfg['tz_name']}', using UTC")
        tz = pytz.utc

    _scheduler = BackgroundScheduler(
        jobstores={"default": MemoryJobStore()},
        executors={"default": ThreadPoolExecutor(max_workers=2)},
        job_defaults={
            "coalesce":      True,   # missed executions → one catch-up run
            "max_instances": 1,      # no overlapping runs of the same job
            "misfire_grace_time": 60,
        },
        timezone=tz,
    )

    # Listen for job events
    _scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    _scheduler.add_listener(_on_job_error,    EVENT_JOB_ERROR)

    # ── Job 1: scrape_opportunities ───────────────────────────────
    from app.scheduler.jobs import run_all_scrapers
    _scheduler.add_job(
        func         = run_all_scrapers,
        trigger      = "interval",
        seconds      = cfg["interval_seconds"],
        id           = "scrape_opportunities",
        name         = "Scrape all opportunity sources",
        replace_existing = True,
    )
    logger.info(
        f"[scheduler] Registered 'scrape_opportunities' — "
        f"{cfg['interval_label']}"
    )

    # ── Job 2: cleanup_expired_opps ───────────────────────────────
    from app.scheduler.jobs import cleanup_expired_opps
    _scheduler.add_job(
        func         = cleanup_expired_opps,
        trigger      = "cron",
        hour         = 1,
        minute       = 0,
        id           = "cleanup_expired",
        name         = "Archive expired opportunities",
        replace_existing = True,
    )
    logger.info("[scheduler] Registered 'cleanup_expired' — daily at 01:00")

    _scheduler.start()
    logger.info(
        f"[scheduler] Started — timezone={cfg['tz_name']} "
        f"scrape_interval={cfg['interval_label']}"
    )

    # ── Optional: run scraper immediately on startup ───────────────
    if cfg["on_startup"]:
        logger.info("[scheduler] RUN_SCRAPER_ON_STARTUP=true — triggering initial run")
        import threading
        t = threading.Thread(target=run_all_scrapers, daemon=True, name="startup-scrape")
        t.start()


def stop() -> None:
    """
    Gracefully shut down the scheduler.
    Called by FastAPI lifespan on application shutdown.
    Waits for running jobs to finish (wait=True).
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        logger.info("[scheduler] Shutting down...")
        _scheduler.shutdown(wait=True)
        logger.info("[scheduler] Stopped")
    _scheduler = None


def get_status() -> dict:
    """Return current scheduler status for the admin API."""
    if _scheduler is None or not _scheduler.running:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id":       job.id,
            "name":     job.name,
            "next_run": next_run.isoformat() if next_run else None,
        })
    return {"running": True, "jobs": jobs}
