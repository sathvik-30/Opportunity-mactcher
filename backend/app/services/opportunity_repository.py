"""
backend/app/services/opportunity_repository.py
─────────────────────────────────────────────────────────────────
The ONLY service responsible for persisting scraped opportunities.
Scrapers do NOT write to the DB directly — they call this.

Pipeline per record:
  validate → compute_hash → dedup_check → insert/update/skip

Uses existing: OpportunityTable, SessionLocal from Phase 1.
─────────────────────────────────────────────────────────────────
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import OpportunityTable
from app.services.deduplicator import compute_content_hash, is_duplicate, normalize_url
from app.services.opportunity_validator import ValidationResult, validate

logger = logging.getLogger(__name__)


def _build_orm_object(clean: dict, content_hash: str) -> OpportunityTable:
    """Convert a validated opportunity dict → OpportunityTable ORM object."""
    now = datetime.now(timezone.utc)
    return OpportunityTable(
        id              = str(uuid.uuid4()),
        title           = clean["title"],
        organization    = clean["organization"],
        type            = clean["type"],
        description     = clean.get("description"),
        required_skills = json.dumps(clean.get("required_skills") or []),
        eligibility     = json.dumps(clean.get("eligibility") or {}),
        deadline        = clean.get("deadline"),
        location        = clean.get("location"),
        stipend         = clean.get("stipend"),
        link            = clean["link"],
        normalized_link = normalize_url(clean["link"]),
        source          = clean.get("source", "unknown"),
        content_hash    = content_hash,
        is_active       = 1,
        last_scraped_at = now,
        created_at      = now,
        updated_at      = now,
    )


def save_opportunity(db: Session, raw: dict) -> dict:
    """
    Persist one opportunity.

    Returns:
      {"status": "inserted",  "opportunity_id": "...", "opportunity": {...}}
      {"status": "updated",   "opportunity_id": "..."}
      {"status": "duplicate", "opportunity_id": "..."}
      {"status": "invalid",   "reason": "..."}
      {"status": "error",     "reason": "..."}

    Does NOT trigger the notification pipeline itself — save_opportunities()
    below does that ONCE for the whole batch of newly-inserted opportunities
    (see notification_service.match_new_opportunities() for why: avoids
    re-querying the full `users` table once per opportunity).
    """
    # ── Validate ──────────────────────────────────────────────────
    result: ValidationResult = validate(raw)
    if not result.valid:
        return {"status": "invalid", "reason": result.reason}

    clean = result.data

    # ── Compute hash ──────────────────────────────────────────────
    content_hash = compute_content_hash(
        clean["organization"],
        clean["title"],
        clean.get("deadline"),
    )

    # ── Dedup check ───────────────────────────────────────────────
    try:
        dup, existing = is_duplicate(db, clean)
    except Exception as e:
        logger.error(f"Dedup check failed: {e}")
        return {"status": "error", "reason": str(e)}

    if dup and existing:
        # Update last_scraped_at so we know it's still active
        try:
            existing.last_scraped_at = datetime.now(timezone.utc)
            existing.is_active = 1
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Could not update last_scraped_at: {e}")
        return {"status": "duplicate", "opportunity_id": existing.id}

    # ── Insert ────────────────────────────────────────────────────
    try:
        opp = _build_orm_object(clean, content_hash)
        db.add(opp)
        db.commit()
        db.refresh(opp)
        logger.debug(f"Inserted: {clean['title'][:60]} — {clean['organization']}")

        return {"status": "inserted", "opportunity_id": opp.id, "opportunity": opp.to_dict()}
    except Exception as e:
        db.rollback()
        # Could be a race condition on content_hash unique constraint
        if "UNIQUE" in str(e).upper():
            return {"status": "duplicate", "reason": "hash conflict"}
        logger.error(f"Insert failed: {e}")
        return {"status": "error", "reason": str(e)}


def save_opportunities(raw_list: list[dict]) -> dict:
    """
    Persist a batch of raw opportunity dicts, then run the notification
    pipeline ONCE for the whole batch of newly-inserted opportunities —
    not once per individual insert. A single scrape run can insert up to
    ~500 opportunities; triggering notification matching per-insert meant
    re-querying the ENTIRE `users` table that many times per run, which
    gets worse as the user base grows. See
    notification_service.match_new_opportunities().

    Returns summary:
      {
        "total": 30,
        "inserted": 21,
        "updated": 0,
        "duplicates": 6,
        "invalid": 1,
        "errors": 2
      }
    """
    summary = {
        "total":      len(raw_list),
        "inserted":   0,
        "updated":    0,
        "duplicates": 0,
        "invalid":    0,
        "errors":     0,
    }

    inserted_opportunities = []

    db: Session = SessionLocal()
    try:
        for raw in raw_list:
            result = save_opportunity(db, raw)
            status = result.get("status", "error")
            if status == "inserted":
                summary["inserted"] += 1
                inserted_opportunities.append(result["opportunity"])
            elif status == "updated":
                summary["updated"] += 1
            elif status == "duplicate":
                summary["duplicates"] += 1
            elif status == "invalid":
                summary["invalid"] += 1
                logger.debug(f"Invalid: {result.get('reason')}")
            else:
                summary["errors"] += 1
                logger.warning(f"Error: {result.get('reason')}")
    finally:
        db.close()

    # Wrapped so a matching/notification failure can never break opportunity
    # persistence, which has already happened above unconditionally.
    if inserted_opportunities:
        try:
            from app.services.notification_service import match_new_opportunities
            match_new_opportunities(inserted_opportunities)
        except Exception as e:
            logger.warning(
                f"Batch match/notify step failed for {len(inserted_opportunities)} "
                f"newly-inserted opportunities: {e}"
            )

    logger.info(
        f"Batch complete — "
        f"total={summary['total']} inserted={summary['inserted']} "
        f"dupes={summary['duplicates']} invalid={summary['invalid']} "
        f"errors={summary['errors']}"
    )
    return summary
