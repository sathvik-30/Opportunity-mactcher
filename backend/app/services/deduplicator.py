"""
backend/app/services/deduplicator.py
─────────────────────────────────────────────────────────────────
Deduplication engine using two signals:
  1. Normalized application URL (primary)
  2. SHA-256 content hash of (organization + title + deadline)

Uses the existing OpportunityTable.content_hash column from Phase 1.
Does NOT create any new tables.
─────────────────────────────────────────────────────────────────
"""

import hashlib
import logging
import re
from urllib.parse import urlparse, urlunparse

from sqlalchemy.orm import Session

from app.database.models import OpportunityTable

logger = logging.getLogger(__name__)


# ── Normalization helpers ─────────────────────────────────────────

def _normalize_text(text: str | None) -> str:
    """Lowercase, strip, collapse whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower().strip())


def normalize_url(url: str | None) -> str | None:
    """
    Normalize a URL for deduplication comparison ONLY — never used as the
    displayed/Apply link itself, since it discards every query parameter
    (not just tracking-only ones like utm_*), the fragment, and a
    trailing slash. Two URLs that only differ in tracking params (or
    scheme host casing, or a trailing slash) normalize to the same
    value. Returns None if url is invalid.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return None
        # Reconstruct without query/fragment for comparison
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",   # params
            "",   # query — stripped for dedup
            "",   # fragment
        ))
        return normalized
    except Exception:
        return None


# ── Hash generation ───────────────────────────────────────────────

def compute_content_hash(organization: str, title: str, deadline: str | None) -> str:
    """
    SHA-256 of normalized (organization + title + deadline).

    "TCS" + "Software Engineer Intern" + "2026-08-20"
    and
    "tcs" + "Software Engineer Intern" + "2026-08-20"
    produce the SAME hash.

    "TCS" + "Software Engineer Intern" + ...
    and
    "Infosys" + "Software Engineer Intern" + ...
    produce DIFFERENT hashes.
    """
    org   = _normalize_text(organization)
    title = _normalize_text(title)
    dl    = _normalize_text(deadline or "")
    raw   = f"{org}|{title}|{dl}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Database duplicate checks ─────────────────────────────────────

def find_by_content_hash(db: Session, content_hash: str) -> OpportunityTable | None:
    """Look up an existing opportunity by its content hash."""
    return (
        db.query(OpportunityTable)
        .filter(OpportunityTable.content_hash == content_hash)
        .first()
    )


def find_by_url(db: Session, url: str) -> OpportunityTable | None:
    """
    Look up an existing opportunity by normalized URL.

    Compares against the stored `normalized_link` column, not the raw
    `link` column — `link` keeps whatever query string the scraper
    originally saw, so comparing the newly-normalized incoming URL
    against a never-normalized stored URL would only match when the
    two scrapes happened to produce byte-identical query strings (rare,
    since sites commonly vary a tracking param like utm_source per
    scrape). Both sides now go through the same normalize_url(), so a
    stored listing and a re-scraped one that only differ by such
    tracking params correctly match here instead of silently falling
    through to the content-hash fallback every time.
    """
    norm = normalize_url(url)
    if not norm:
        return None
    return (
        db.query(OpportunityTable)
        .filter(OpportunityTable.normalized_link == norm)
        .first()
    )


def is_duplicate(db: Session, opportunity: dict) -> tuple[bool, OpportunityTable | None]:
    """
    Check if an opportunity already exists in the database.

    Signal 1 (primary): URL match
    Signal 2 (fallback): content hash match

    Returns: (is_dup: bool, existing_row: OpportunityTable | None)
    """
    link = opportunity.get("link")
    if link:
        existing = find_by_url(db, link)
        if existing:
            logger.debug(f"Duplicate by URL: {link[:60]}")
            return True, existing

    # Fallback: hash
    content_hash = compute_content_hash(
        opportunity.get("organization", ""),
        opportunity.get("title", ""),
        opportunity.get("deadline"),
    )
    existing = find_by_content_hash(db, content_hash)
    if existing:
        logger.debug(f"Duplicate by hash: {opportunity.get('title', '')[:50]}")
        return True, existing

    return False, None
