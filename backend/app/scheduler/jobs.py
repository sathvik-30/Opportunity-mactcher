"""
backend/app/scheduler/jobs.py
─────────────────────────────────────────────────────────────────
Defines all scheduled jobs.

SCRAPER REGISTRY:
  Add new scrapers to SCRAPER_REGISTRY list.
  The scheduler job will automatically run all registered scrapers.
  Phase 4 scrapers: just append to SCRAPER_REGISTRY — no other
  changes needed.

JOBS:
  run_all_scrapers()        — runs every registered scraper
  cleanup_expired_opps()   — archives past-deadline opportunities

Both jobs manage their own DB sessions (never reuse request sessions).
One scraper failing never stops the others.
─────────────────────────────────────────────────────────────────
"""

import logging
import time
import uuid
from datetime import date, datetime, timezone

from app.database.connection import SessionLocal
from app.database.models import OpportunityTable, ScraperLogTable

logger = logging.getLogger(__name__)

# ── Scraper Registry ──────────────────────────────────────────────
# To add a new scraper in Phase 4, import it and append to this list.
# Scheduler logic does NOT need to change.
from app.scrapers.nsp import NSPScraper
from app.scrapers.simplifyjobs import SimplifyJobsScraper

# NOTE — Devfolio was evaluated for Phase 4 and found NOT SUITABLE
# for automated collection (client-side-rendered SPA with no public
# API — see Phase 4 report). It is intentionally not registered here.
SCRAPER_REGISTRY = [
    SimplifyJobsScraper,
    NSPScraper,
]


# ── Internal: run one scraper and write its log row ───────────────

def _run_single_scraper(scraper_class) -> dict:
    """
    Run one scraper safely.
    Always returns a summary dict regardless of success/failure.
    Writes one ScraperLogTable row to the database.
    """
    from app.services.opportunity_repository import save_opportunities

    scraper_name = getattr(scraper_class, "source_name", scraper_class.__name__)
    log_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    db = SessionLocal()
    log_row = ScraperLogTable(
        id         = log_id,
        source     = scraper_name,
        status     = "running",
        started_at = started_at,
    )
    db.add(log_row)
    db.commit()

    summary = {
        "source":     scraper_name,
        "status":     "failed",
        "fetched":    0,
        "inserted":   0,
        "updated":    0,
        "duplicates": 0,
        "invalid":    0,
        "errors":     0,
        "error":      None,
    }

    t_start = time.time()
    try:
        logger.info(f"[jobs] Starting scraper: {scraper_name}")
        scraper = scraper_class()

        # ── Attempt with up to 3 retries on transient errors ──────
        run_result = None
        last_error = None
        for attempt in range(1, 4):
            try:
                run_result = scraper.run()
                break  # success
            except Exception as e:
                last_error = str(e)
                # Only retry on connection/timeout-style errors
                err_lower = str(e).lower()
                is_transient = any(kw in err_lower for kw in [
                    "timeout", "connection", "temporary", "503", "502", "429"
                ])
                if is_transient and attempt < 3:
                    wait = attempt * 5  # 5s, 10s backoff
                    logger.warning(
                        f"[jobs] {scraper_name} attempt {attempt} failed "
                        f"({e}), retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    raise

        if run_result is None:
            raise RuntimeError(last_error or "Scraper returned no result")

        summary["fetched"] = run_result.get("fetched", 0)

        # ── Persist via repository ─────────────────────────────────
        if run_result.get("opportunities"):
            persist_summary = save_opportunities(run_result["opportunities"])
            summary["inserted"]   = persist_summary["inserted"]
            summary["updated"]    = persist_summary["updated"]
            summary["duplicates"] = persist_summary["duplicates"]
            summary["invalid"]    = persist_summary["invalid"]
            summary["errors"]     = persist_summary["errors"]

        summary["status"] = "success"
        logger.info(
            f"[jobs] {scraper_name} done — "
            f"fetched={summary['fetched']} inserted={summary['inserted']} "
            f"dupes={summary['duplicates']}"
        )

    except Exception as e:
        summary["status"] = "failed"
        summary["error"]  = str(e)
        logger.error(f"[jobs] {scraper_name} FAILED: {e}")

    finally:
        finished_at  = datetime.now(timezone.utc)
        duration_ms  = int((time.time() - t_start) * 1000)
        try:
            log_row.status            = summary["status"]
            log_row.total_found       = summary["fetched"]
            log_row.inserted          = summary["inserted"]
            log_row.updated           = summary["updated"]
            log_row.duplicates_skipped = summary["duplicates"]
            log_row.errors            = summary["errors"] + (
                1 if summary["status"] == "failed" else 0
            )
            log_row.error_details     = summary.get("error")
            log_row.finished_at       = finished_at
            log_row.duration_ms       = duration_ms
            db.commit()
        except Exception as log_err:
            logger.error(f"[jobs] Could not write scraper log: {log_err}")
            db.rollback()
        finally:
            db.close()

    return summary


# ── Public job: run all scrapers ──────────────────────────────────

def run_all_scrapers() -> list[dict]:
    """
    Run every scraper in SCRAPER_REGISTRY sequentially.
    One failure does NOT stop the others.

    Called by:
      - APScheduler on schedule
      - POST /admin/trigger-scraper (same function, zero duplication)

    Returns list of per-scraper summary dicts.
    """
    logger.info(f"[jobs] run_all_scrapers — {len(SCRAPER_REGISTRY)} scraper(s)")
    results = []
    for scraper_class in SCRAPER_REGISTRY:
        try:
            result = _run_single_scraper(scraper_class)
            results.append(result)
        except Exception as e:
            # Should never reach here (handled inside _run_single_scraper)
            # but defensive catch so one broken scraper class can't
            # prevent the rest from running
            name = getattr(scraper_class, "source_name", str(scraper_class))
            logger.error(f"[jobs] Unexpected error running {name}: {e}")
            results.append({
                "source": name, "status": "failed",
                "error": str(e)
            })
    logger.info("[jobs] run_all_scrapers complete")
    return results


# ── Public job: archive expired opportunities ─────────────────────

def cleanup_expired_opps() -> dict:
    """
    Archive opportunities whose deadline has passed.
    Sets is_active=0. NEVER deletes rows (kept for analytics).
    Opportunities with deadline=None are never touched.
    Runs once per day via scheduler.
    """
    logger.info("[jobs] cleanup_expired_opps started")
    today_str = date.today().isoformat()   # "2026-08-05"
    archived  = 0
    db = SessionLocal()
    try:
        # Only consider rows that are active AND have a non-null deadline
        candidates = (
            db.query(OpportunityTable)
            .filter(
                OpportunityTable.is_active == 1,
                OpportunityTable.deadline.isnot(None),
                OpportunityTable.deadline != "",
                OpportunityTable.deadline < today_str,
            )
            .all()
        )
        for opp in candidates:
            opp.is_active = 0
            archived += 1
        db.commit()
        logger.info(f"[jobs] Archived {archived} expired opportunities")
    except Exception as e:
        db.rollback()
        logger.error(f"[jobs] cleanup_expired_opps failed: {e}")
    finally:
        db.close()

    return {"archived": archived, "as_of": today_str}
