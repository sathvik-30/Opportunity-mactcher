"""
backend/app/routes/admin.py
─────────────────────────────────────────────────────────────────
Admin endpoints for scheduler monitoring, manual control, and
(Phase 8) full system monitoring: users, opportunities, scrapers,
notifications, emails, match statistics.

SECURITY (Phase 8):
  Every route in this file now requires require_admin — valid JWT
  AND is_admin=1 on the authenticated user. Previously (Phase 3-7)
  these routes had inconsistent/no protection; this was a real gap
  closed as part of Phase 8's security requirements, not scope creep.
  A normal student now gets 403 on every /admin/* route.

Routes:
  GET  /admin/scraper-status      — (legacy, Phase 3) recent scraper logs
  GET  /admin/scheduler-status    — live scheduler job status
  POST /admin/trigger-scraper     — manually trigger scraper pipeline
  GET  /admin/db-stats            — (legacy, Phase 4) quick opportunity counts

  GET  /admin/stats               — (Phase 8) full system statistics
  GET  /admin/users               — (Phase 8) paginated user list
  GET  /admin/opportunities       — (Phase 8) paginated opportunity list
  GET  /admin/scrapers            — (Phase 8) scraper logs + per-source health
  GET  /admin/notifications       — (Phase 8) notification statistics
  GET  /admin/emails              — (Phase 8) email statistics
─────────────────────────────────────────────────────────────────
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func

from app.database.connection import SessionLocal, get_db
from app.database.models import (
    EmailHistoryTable,
    NotificationTable,
    OpportunityTable,
    SavedOpportunityTable,
    ScraperLogTable,
    UserTable,
)
from app.services.auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

MAX_LIMIT = 100
DEFAULT_LIMIT = 20


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, MAX_LIMIT))


# ═══════════════════════════════════════════════════════════════
# LEGACY ROUTES (Phase 3/4) — kept, now admin-protected
# ═══════════════════════════════════════════════════════════════

@router.get("/scraper-status")
def get_scraper_status(
    limit: int = Query(default=10, ge=1, le=100),
    _admin: UserTable = Depends(require_admin),
):
    """Recent scraper execution logs. Newest first."""
    db = SessionLocal()
    try:
        rows = (
            db.query(ScraperLogTable)
            .order_by(desc(ScraperLogTable.started_at))
            .limit(limit)
            .all()
        )
        logs = [{
            "id":                 row.id,
            "source":             row.source,
            "status":             row.status,
            "started_at":         row.started_at.isoformat() if row.started_at else None,
            "finished_at":        row.finished_at.isoformat() if row.finished_at else None,
            "duration_ms":        row.duration_ms,
            "total_found":        row.total_found,
            "inserted":           row.inserted,
            "updated":            row.updated,
            "duplicates_skipped": row.duplicates_skipped,
            "errors":             row.errors,
            "error_details":      row.error_details,
        } for row in rows]
        return {"count": len(logs), "logs": logs}
    finally:
        db.close()


@router.get("/scheduler-status")
def get_scheduler_status(_admin: UserTable = Depends(require_admin)):
    """Live APScheduler state: running, registered jobs, next run times."""
    from app.scheduler.runner import get_status
    return get_status()


@router.post("/trigger-scraper")
def trigger_scraper(_admin: UserTable = Depends(require_admin)):
    """
    Manually trigger the full scraper pipeline. Uses the SAME
    run_all_scrapers() the scheduler uses — zero duplication.
    """
    logger.info(f"[admin] Manual scraper trigger requested by {_admin.email}")
    from app.scheduler.jobs import run_all_scrapers

    try:
        results = run_all_scrapers()
        total_inserted   = sum(r.get("inserted", 0) for r in results)
        total_duplicates = sum(r.get("duplicates", 0) for r in results)
        total_fetched    = sum(r.get("fetched", 0) for r in results)
        failed_scrapers  = [r["source"] for r in results if r.get("status") == "failed"]

        return {
            "message":          "Scraper pipeline completed",
            "scrapers":         len(results),
            "total_fetched":    total_fetched,
            "total_inserted":   total_inserted,
            "total_duplicates": total_duplicates,
            "failed_scrapers":  failed_scrapers,
            "details":          results,
        }
    except Exception as e:
        logger.error(f"[admin] trigger-scraper failed: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Scraper pipeline error")


@router.get("/db-stats")
def get_db_stats(_admin: UserTable = Depends(require_admin)):
    """Quick database stats: total opportunities, active, by source."""
    db = SessionLocal()
    try:
        total_opps  = db.query(OpportunityTable).count()
        active_opps = db.query(OpportunityTable).filter(OpportunityTable.is_active == 1).count()
        total_users = db.query(UserTable).count()

        source_counts = (
            db.query(OpportunityTable.source, func.count(OpportunityTable.id))
            .group_by(OpportunityTable.source)
            .all()
        )
        by_source = {src: cnt for src, cnt in source_counts}

        return {
            "opportunities": {
                "total": total_opps, "active": active_opps,
                "expired": total_opps - active_opps, "by_source": by_source,
            },
            "users": {"total": total_users},
        }
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# PHASE 8 — GET /admin/stats
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
def get_admin_stats(db=Depends(get_db), _admin: UserTable = Depends(require_admin)):
    """
    Full system statistics. Every number is a real aggregate query —
    nothing here is estimated or hardcoded.

    NOTE on "active_users": UserTable has no login-tracking field
    (no last_login), so a login-activity definition of "active" isn't
    derivable from current data. Rather than fabricate one, this
    endpoint defines active_users as students who have EITHER saved
    an opportunity OR received a notification — i.e. genuine platform
    engagement, computed from real relational data. Documented here
    so the number's meaning is never a mystery.
    """
    total_users = db.query(func.count(UserTable.id)).scalar() or 0

    engaged_user_ids = {
        r[0] for r in db.query(SavedOpportunityTable.user_id).distinct().all()
    } | {
        r[0] for r in db.query(NotificationTable.user_id).distinct().all()
    }

    total_opps  = db.query(func.count(OpportunityTable.id)).scalar() or 0
    active_opps = db.query(func.count(OpportunityTable.id)).filter(OpportunityTable.is_active == 1).scalar() or 0

    type_counts = dict(
        db.query(OpportunityTable.type, func.count(OpportunityTable.id))
        .group_by(OpportunityTable.type).all()
    )

    saved_count = db.query(func.count(SavedOpportunityTable.id)).scalar() or 0

    total_notifs  = db.query(func.count(NotificationTable.id)).scalar() or 0
    unread_notifs = db.query(func.count(NotificationTable.id)).filter(NotificationTable.is_read == 0).scalar() or 0

    emails_sent   = db.query(func.count(EmailHistoryTable.id)).filter(EmailHistoryTable.status == "sent").scalar() or 0
    emails_failed = db.query(func.count(EmailHistoryTable.id)).filter(EmailHistoryTable.status == "failed").scalar() or 0

    scraper_runs       = db.query(func.count(ScraperLogTable.id)).scalar() or 0
    scraper_failures   = db.query(func.count(ScraperLogTable.id)).filter(ScraperLogTable.status == "failed").scalar() or 0
    scraper_successes  = db.query(func.count(ScraperLogTable.id)).filter(ScraperLogTable.status == "success").scalar() or 0

    return {
        "users": {
            "total": total_users,
            "active_engaged": len(engaged_user_ids),  # see docstring for definition
        },
        "opportunities": {
            "total":  total_opps,
            "active": active_opps,
            "expired": total_opps - active_opps,
            "by_type": {
                "internship":  type_counts.get("internship", 0),
                "job":         type_counts.get("job", 0),
                "hackathon":   type_counts.get("hackathon", 0),
                "scholarship": type_counts.get("scholarship", 0),
                "research":    type_counts.get("research", 0),
            },
        },
        "saved_opportunities": saved_count,
        "notifications": {
            "total": total_notifs,
            "unread": unread_notifs,
        },
        "emails": {
            "sent": emails_sent,
            "failed": emails_failed,
        },
        "scrapers": {
            "total_runs": scraper_runs,
            "failures": scraper_failures,
            "successes": scraper_successes,
        },
    }


# ═══════════════════════════════════════════════════════════════
# PHASE 8 — GET /admin/users
# ═══════════════════════════════════════════════════════════════

@router.get("/users")
def get_admin_users(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db=Depends(get_db),
    _admin: UserTable = Depends(require_admin),
):
    """
    Paginated, safe user summary. NEVER returns password, JWT, or any
    credential. saved_count/notification_count come from two grouped
    aggregate queries (not per-user N+1 queries).
    """
    limit = _clamp_limit(limit)
    offset = (page - 1) * limit

    total = db.query(func.count(UserTable.id)).scalar() or 0
    users = (
        db.query(UserTable)
        .order_by(desc(UserTable.created_at))
        .offset(offset).limit(limit)
        .all()
    )
    user_ids = [u.id for u in users]

    saved_counts = dict(
        db.query(SavedOpportunityTable.user_id, func.count(SavedOpportunityTable.id))
        .filter(SavedOpportunityTable.user_id.in_(user_ids))
        .group_by(SavedOpportunityTable.user_id).all()
    ) if user_ids else {}

    notif_counts = dict(
        db.query(NotificationTable.user_id, func.count(NotificationTable.id))
        .filter(NotificationTable.user_id.in_(user_ids))
        .group_by(NotificationTable.user_id).all()
    ) if user_ids else {}

    results = [{
        "id":                   u.id,
        "name":                 u.name,
        "email":                u.email,
        "branch":               u.branch,
        "year":                 u.year,
        "created_at":           u.created_at.isoformat() if u.created_at else None,
        "email_notifications":  bool(u.email_notifications),
        "is_admin":             bool(u.is_admin),
        "saved_count":          saved_counts.get(u.id, 0),
        "notification_count":   notif_counts.get(u.id, 0),
    } for u in users]

    return {
        "page": page, "limit": limit, "total": total,
        "total_pages": (total + limit - 1) // limit if limit else 0,
        "users": results,
    }


# ═══════════════════════════════════════════════════════════════
# PHASE 8 — GET /admin/opportunities
# ═══════════════════════════════════════════════════════════════

@router.get("/opportunities")
def get_admin_opportunities(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    source: str | None = Query(default=None),
    type: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    db=Depends(get_db),
    _admin: UserTable = Depends(require_admin),
):
    """
    Paginated, filterable opportunity list for admin review. Deliberately
    omits the full `description` field (can be long) — everything else
    needed to triage a listing is included.
    """
    limit = _clamp_limit(limit)
    offset = (page - 1) * limit

    q = db.query(OpportunityTable)
    if source:
        q = q.filter(OpportunityTable.source == source)
    if type:
        q = q.filter(OpportunityTable.type == type)
    if active is not None:
        q = q.filter(OpportunityTable.is_active == (1 if active else 0))
    if search:
        like = f"%{search}%"
        # Parameterized via SQLAlchemy's .ilike — never raw string
        # concatenation, so this is not SQL-injectable.
        q = q.filter(
            OpportunityTable.title.ilike(like) | OpportunityTable.organization.ilike(like)
        )

    total = q.count()
    rows = q.order_by(desc(OpportunityTable.created_at)).offset(offset).limit(limit).all()

    results = [{
        "id":              o.id,
        "title":           o.title,
        "organization":    o.organization,
        "type":            o.type,
        "source":          o.source,
        "deadline":        o.deadline,
        "is_active":       bool(o.is_active),
        "created_at":      o.created_at.isoformat() if o.created_at else None,
        "last_scraped_at": o.last_scraped_at.isoformat() if o.last_scraped_at else None,
        "link":            o.link,
    } for o in rows]

    return {
        "page": page, "limit": limit, "total": total,
        "total_pages": (total + limit - 1) // limit if limit else 0,
        "opportunities": results,
    }


# ═══════════════════════════════════════════════════════════════
# PHASE 8 — GET /admin/scrapers  (logs + per-source health)
# ═══════════════════════════════════════════════════════════════

@router.get("/scrapers")
def get_admin_scrapers(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    source: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db=Depends(get_db),
    _admin: UserTable = Depends(require_admin),
):
    """
    Recent scraper executions (paginated, filterable) PLUS a per-source
    health summary. Health is computed entirely from real ScraperLogTable
    rows — never fabricated. Pulls the most recent 200 logs in one query
    and groups by source in Python; this dataset is small in practice
    (a handful of registered scrapers), so this avoids both N+1 queries
    and unnecessary window-function complexity for the data volume here.
    """
    limit = _clamp_limit(limit)
    offset = (page - 1) * limit

    q = db.query(ScraperLogTable)
    if source:
        q = q.filter(ScraperLogTable.source == source)
    if status:
        q = q.filter(ScraperLogTable.status == status)

    total = q.count()
    rows = q.order_by(desc(ScraperLogTable.started_at)).offset(offset).limit(limit).all()

    logs = [{
        "id":                 r.id,
        "source":             r.source,
        "status":             r.status,
        "started_at":         r.started_at.isoformat() if r.started_at else None,
        "finished_at":        r.finished_at.isoformat() if r.finished_at else None,
        "duration_ms":        r.duration_ms,
        "fetched":            r.total_found,
        "inserted":           r.inserted,
        "updated":            r.updated,
        "duplicates":         r.duplicates_skipped,
        "invalid":            None,  # not tracked separately from duplicates in ScraperLogTable
        "errors":             r.errors,
        "error_message":      r.error_details,
    } for r in rows]

    # ── Per-source health (Step 11/12) ──────────────────────────
    recent = (
        db.query(ScraperLogTable)
        .order_by(desc(ScraperLogTable.started_at))
        .limit(200)
        .all()
    )
    by_source: dict[str, list] = {}
    for r in recent:
        by_source.setdefault(r.source, []).append(r)

    health = []
    for src, runs in by_source.items():
        runs_sorted = sorted(runs, key=lambda r: r.started_at, reverse=True)
        last_run = runs_sorted[0]
        last_success = next((r for r in runs_sorted if r.status == "success"), None)
        last_failure = next((r for r in runs_sorted if r.status == "failed"), None)
        successes = sum(1 for r in runs_sorted if r.status == "success")
        success_rate = round(100 * successes / len(runs_sorted)) if runs_sorted else 0

        if last_run.status == "success":
            health_status = "Healthy"
        elif last_success is not None:
            health_status = "Warning"  # has failed recently but has succeeded before
        else:
            health_status = "Failed"   # never succeeded in the sampled window

        health.append({
            "source": src,
            "status": health_status,
            "last_run_at": last_run.started_at.isoformat() if last_run.started_at else None,
            "last_run_status": last_run.status,
            "last_success_at": last_success.started_at.isoformat() if last_success else None,
            "last_failure_at": last_failure.started_at.isoformat() if last_failure else None,
            "last_failure_reason": last_failure.error_details if last_failure else None,
            "success_rate_pct": success_rate,
            "runs_sampled": len(runs_sorted),
        })

    failed_recent = [
        {
            "source": r.source,
            "reason": r.error_details,
            "time": r.started_at.isoformat() if r.started_at else None,
        }
        for r in recent if r.status == "failed"
    ][:20]

    return {
        "page": page, "limit": limit, "total": total,
        "total_pages": (total + limit - 1) // limit if limit else 0,
        "logs": logs,
        "health": health,
        "recent_failures": failed_recent,
    }


# ═══════════════════════════════════════════════════════════════
# PHASE 8 — GET /admin/notifications
# ═══════════════════════════════════════════════════════════════

@router.get("/notifications")
def get_admin_notifications(db=Depends(get_db), _admin: UserTable = Depends(require_admin)):
    """Notification statistics — all real aggregate queries."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    total  = db.query(func.count(NotificationTable.id)).scalar() or 0
    unread = db.query(func.count(NotificationTable.id)).filter(NotificationTable.is_read == 0).scalar() or 0
    read   = total - unread

    today_count = (
        db.query(func.count(NotificationTable.id))
        .filter(NotificationTable.created_at >= today_start).scalar() or 0
    )
    week_count = (
        db.query(func.count(NotificationTable.id))
        .filter(NotificationTable.created_at >= week_start).scalar() or 0
    )

    by_type = dict(
        db.query(NotificationTable.type, func.count(NotificationTable.id))
        .group_by(NotificationTable.type).all()
    )

    # Top matched opportunities (by notification count) — real data,
    # only included if any notifications reference a real opportunity.
    top_rows = (
        db.query(
            NotificationTable.opportunity_id,
            OpportunityTable.title,
            func.count(NotificationTable.id).label("cnt"),
        )
        .join(OpportunityTable, OpportunityTable.id == NotificationTable.opportunity_id)
        .group_by(NotificationTable.opportunity_id, OpportunityTable.title)
        .order_by(desc("cnt"))
        .limit(5)
        .all()
    )
    top_matched = [{"opportunity_id": r[0], "title": r[1], "notification_count": r[2]} for r in top_rows]

    return {
        "total": total, "read": read, "unread": unread,
        "today": today_count, "this_week": week_count,
        "by_type": by_type,
        "top_matched_opportunities": top_matched,
    }


# ═══════════════════════════════════════════════════════════════
# PHASE 8 — GET /admin/emails
# ═══════════════════════════════════════════════════════════════

@router.get("/emails")
def get_admin_emails(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db=Depends(get_db),
    _admin: UserTable = Depends(require_admin),
):
    """
    Email statistics + a page of recent failed emails for triage.
    NEVER exposes SMTP credentials — EmailHistoryTable doesn't store
    them (only recipient_email, status, error_message), so there's
    nothing to accidentally leak here.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    total   = db.query(func.count(EmailHistoryTable.id)).scalar() or 0
    sent    = db.query(func.count(EmailHistoryTable.id)).filter(EmailHistoryTable.status == "sent").scalar() or 0
    failed  = db.query(func.count(EmailHistoryTable.id)).filter(EmailHistoryTable.status == "failed").scalar() or 0
    pending = db.query(func.count(EmailHistoryTable.id)).filter(EmailHistoryTable.status == "pending").scalar() or 0
    skipped = db.query(func.count(EmailHistoryTable.id)).filter(EmailHistoryTable.status == "skipped").scalar() or 0

    today_count = (
        db.query(func.count(EmailHistoryTable.id))
        .filter(EmailHistoryTable.created_at >= today_start).scalar() or 0
    )
    week_count = (
        db.query(func.count(EmailHistoryTable.id))
        .filter(EmailHistoryTable.created_at >= week_start).scalar() or 0
    )

    attempted = sent + failed
    success_rate = round(100 * sent / attempted) if attempted else None

    limit = _clamp_limit(limit)
    offset = (page - 1) * limit
    failed_q = db.query(EmailHistoryTable).filter(EmailHistoryTable.status == "failed")
    failed_total = failed_q.count()
    failed_rows = (
        failed_q.order_by(desc(EmailHistoryTable.created_at)).offset(offset).limit(limit).all()
    )
    recent_failed = [{
        "id":              r.id,
        "recipient_email": r.recipient_email,
        "opportunity_id":  r.opportunity_id,
        "subject":         r.subject,
        "error_message":   r.error_message,
        "retry_count":     r.retry_count,
        "created_at":      r.created_at.isoformat() if r.created_at else None,
    } for r in failed_rows]

    return {
        "total": total, "sent": sent, "failed": failed,
        "pending": pending, "skipped": skipped,
        "today": today_count, "this_week": week_count,
        "success_rate_pct": success_rate,
        "recent_failed": {
            "page": page, "limit": limit, "total": failed_total,
            "items": recent_failed,
        },
    }
