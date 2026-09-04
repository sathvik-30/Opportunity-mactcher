"""
database/migrations.py
Creates all tables on startup and seeds sample_opportunities.json into DB.
Safe to call multiple times — idempotent.
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal, engine
from app.database.models import Base, OpportunityTable
from app.services.deduplicator import normalize_url


def create_tables() -> None:
    """Create all SQLAlchemy tables. Uses CREATE TABLE IF NOT EXISTS internally."""
    from app.database import models  # noqa — import triggers model registration
    Base.metadata.create_all(bind=engine)
    print("[DB] Tables created (or already exist)")


def _add_missing_columns() -> None:
    """
    Phase 6: lightweight, additive migration for SQLite.

    Base.metadata.create_all() only creates tables that don't exist yet —
    it does NOT add new columns to tables that already exist on disk. Since
    Phase 6 adds columns to `users` (notification preferences, match-engine
    profile fields) and `notifications` (match_score), any database created
    before Phase 6 needs those columns added explicitly.

    Never drops or modifies existing columns/data. Safe to run on every
    startup — checks PRAGMA-derived column info first and only adds what's
    missing.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    additions = {
        "users": [
            ("notify_internship",  "INTEGER DEFAULT 1"),
            ("notify_job",         "INTEGER DEFAULT 1"),
            ("notify_hackathon",   "INTEGER DEFAULT 1"),
            ("notify_scholarship", "INTEGER DEFAULT 1"),
            ("notify_research",    "INTEGER DEFAULT 1"),
            ("notify_remote_only", "INTEGER DEFAULT 0"),
            ("preferred_role",     "VARCHAR(200)"),
            ("preferred_location", "VARCHAR(200)"),
            ("remote_preference",  "VARCHAR(20)"),
            ("is_admin",           "INTEGER DEFAULT 0"),
        ],
        "notifications": [
            ("match_score", "INTEGER"),
        ],
        "opportunities": [
            ("normalized_link", "TEXT"),
        ],
    }

    with engine.connect() as conn:
        for table, columns in additions.items():
            if table not in existing_tables:
                continue  # create_tables() above will have made it fresh, all columns included
            existing_cols = {c["name"] for c in inspector.get_columns(table)}
            for col_name, ddl_type in columns:
                if col_name in existing_cols:
                    continue
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {ddl_type}"))
                    conn.commit()
                    print(f"[DB] Migrated: added column {table}.{col_name}")
                except Exception as e:
                    print(f"[DB] Column migration skipped for {table}.{col_name}: {e}")


def _backfill_normalized_links() -> None:
    """
    Populate normalized_link for any opportunity row that doesn't have
    it yet. Covers two cases: rows that existed before this column was
    added, and rows inserted via seed_database() below (which sets
    `link` but not `normalized_link` — only the scraper insert path in
    opportunity_repository.py computes it directly). Safe to run every
    startup: only touches rows where normalized_link IS NULL, and never
    modifies `link` itself (the real Apply-button URL).
    """
    db: Session = SessionLocal()
    try:
        rows = (
            db.query(OpportunityTable)
            .filter(OpportunityTable.normalized_link.is_(None))
            .all()
        )
        if not rows:
            return
        updated = 0
        for row in rows:
            norm = normalize_url(row.link)
            if norm:
                row.normalized_link = norm
                updated += 1
        db.commit()
        print(f"[DB] Backfilled normalized_link for {updated}/{len(rows)} opportunities")
    except Exception as e:
        db.rollback()
        print(f"[DB] normalized_link backfill failed: {e}")
    finally:
        db.close()


def _compute_hash(title: str, organization: str, deadline: str) -> str:
    """SHA256 deduplication hash: prevents same opportunity being inserted twice."""
    raw = f"{title.lower().strip()}|{organization.lower().strip()}|{deadline or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def seed_database() -> None:
    """
    Load sample_opportunities.json into DB.
    Only runs if the opportunities table is empty.
    Existing data is never overwritten.
    """
    db: Session = SessionLocal()
    try:
        count = db.query(OpportunityTable).count()
        if count > 0:
            print(f"[DB] Seed skipped — {count} opportunities already in database")
            return

        # Locate the JSON file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.normpath(
            os.path.join(base_dir, "../../../data/sample_opportunities.json")
        )

        if not os.path.exists(json_path):
            print(f"[DB] Seed file not found at {json_path} — skipping")
            return

        with open(json_path, encoding="utf-8") as f:
            records = json.load(f)

        inserted = 0
        for record in records:
            content_hash = _compute_hash(
                record.get("title", ""),
                record.get("organization", ""),
                record.get("deadline", ""),
            )

            exists = db.query(OpportunityTable).filter(
                OpportunityTable.content_hash == content_hash
            ).first()
            if exists:
                continue

            opp = OpportunityTable(
                id              = record.get("id") or str(uuid.uuid4()),
                title           = record["title"],
                organization    = record["organization"],
                type            = record["type"],
                description     = record.get("description", ""),
                required_skills = json.dumps(record.get("required_skills", [])),
                eligibility     = json.dumps(record.get("eligibility", {})),
                deadline        = record.get("deadline"),
                location        = record.get("location"),
                stipend         = record.get("stipend"),
                link            = record["link"],
                source          = "manual",
                content_hash    = content_hash,
                is_active       = 1,
                created_at      = datetime.now(timezone.utc),
                updated_at      = datetime.now(timezone.utc),
            )
            db.add(opp)
            inserted += 1

        db.commit()
        print(f"[DB] Seeded {inserted} opportunities from sample_opportunities.json")

    except Exception as e:
        db.rollback()
        print(f"[DB] Seed failed: {e}")
        raise
    finally:
        db.close()


def run_migrations() -> None:
    """Master startup function: create tables, add any missing columns, then seed data."""
    create_tables()
    _add_missing_columns()
    seed_database()
    _backfill_normalized_links()
