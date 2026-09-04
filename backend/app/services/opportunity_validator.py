"""
backend/app/services/opportunity_validator.py
─────────────────────────────────────────────────────────────────
Validates and cleans scraped opportunities before DB insertion.
NEVER uses an LLM to fill missing fields.
Missing optional fields become None or [].
─────────────────────────────────────────────────────────────────
"""

import logging
import re
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

VALID_TYPES = {
    "internship", "job", "hackathon", "scholarship",
    "fellowship", "research", "competition", "open_source",
}

# Maps common synonyms from scrapers → canonical types
TYPE_ALIASES = {
    "full_time": "job",
    "full-time": "job",
    "part_time": "job",
    "contract": "job",
    "software": "internship",
    "engineering": "internship",
    "intern": "internship",
    "co-op": "internship",
    "coop": "internship",
    "contest": "competition",
    "open source": "open_source",
    "opensource": "open_source",
    "grant": "fellowship",
    "stipend": "fellowship",
    "phd": "research",
    "postdoc": "research",
}


def _clean_str(value) -> str | None:
    """Strip and normalize whitespace. Return None if empty."""
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned if cleaned else None


def _is_valid_url(url: str | None) -> bool:
    """Return True only if url is a well-formed http/https URL."""
    if not url:
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _normalize_type(raw_type: str | None) -> str | None:
    """Map raw type string → one of VALID_TYPES, or None if unrecognizable."""
    if not raw_type:
        return None
    t = raw_type.lower().strip().replace(" ", "_")
    if t in VALID_TYPES:
        return t
    alias = TYPE_ALIASES.get(t)
    if alias:
        return alias
    # Partial match
    for valid in VALID_TYPES:
        if valid in t or t in valid:
            return valid
    return None


def _normalize_date(raw_date: str | None) -> str | None:
    """
    Try to parse raw_date into YYYY-MM-DD.
    Returns None if the date cannot be reliably determined.
    NEVER guesses or invents a deadline.
    """
    if not raw_date:
        return None
    raw = str(raw_date).strip()
    if not raw:
        return None

    # Already in YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            return None

    # Try common formats
    formats = [
        "%B %d, %Y",    # July 20, 2025
        "%b %d, %Y",    # Jul 20, 2025
        "%d %B %Y",     # 20 July 2025
        "%d %b %Y",     # 20 Jul 2025
        "%m/%d/%Y",     # 07/20/2025
        "%d/%m/%Y",     # 20/07/2025
        "%Y/%m/%d",     # 2025/07/20
        "%d-%m-%Y",     # 20-07-2025
        "%B %Y",        # July 2025 → use last day of month
        "%b %Y",        # Jul 2025
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Unix timestamp (integer)
    if re.match(r"^\d{9,10}$", raw):
        try:
            dt = datetime.fromtimestamp(int(raw))
            return dt.strftime("%Y-%m-%d")
        except Exception as e:
            logger.debug(f"Could not parse unix timestamp {raw!r}: {e}")

    logger.debug(f"Could not parse date: {raw!r}")
    return None


def _normalize_skills(raw_skills) -> list[str]:
    """
    Return a deduplicated list of skill strings.
    Accepts list or comma-separated string.
    """
    if not raw_skills:
        return []
    if isinstance(raw_skills, str):
        items = [s.strip() for s in raw_skills.split(",")]
    elif isinstance(raw_skills, list):
        items = [str(s).strip() for s in raw_skills]
    else:
        return []

    # Deduplicate preserving order, remove empty strings
    seen = set()
    result = []
    for item in items:
        if item and item.lower() not in seen:
            seen.add(item.lower())
            result.append(item)
    return result


def _normalize_location(raw_location) -> str | None:
    """Normalize location. Accepts list or string."""
    if not raw_location:
        return None
    if isinstance(raw_location, list):
        if not raw_location:
            return None
        # Join multiple locations
        cleaned = [_clean_str(loc) for loc in raw_location if _clean_str(loc)]
        return " | ".join(cleaned) if cleaned else None
    return _clean_str(raw_location)


class ValidationResult:
    """Holds the result of validating one opportunity."""
    def __init__(self, valid: bool, data: dict | None = None, reason: str = ""):
        self.valid = valid
        self.data = data
        self.reason = reason

    def __bool__(self):
        return self.valid


def validate(raw: dict) -> ValidationResult:
    """
    Validate and clean one raw opportunity dict.

    Returns ValidationResult:
      .valid = True  → .data contains clean dict ready for DB
      .valid = False → .reason explains what failed

    Required fields: title, organization, link
    Optional: type defaults to "internship"
    """
    if not isinstance(raw, dict):
        return ValidationResult(False, reason="Not a dict")

    # ── Required: title ───────────────────────────────────────────
    title = _clean_str(raw.get("title"))
    if not title:
        return ValidationResult(False, reason="Missing title")
    if len(title) > 500:
        title = title[:500]

    # ── Required: organization ────────────────────────────────────
    org = _clean_str(raw.get("organization") or raw.get("company_name") or raw.get("company"))
    if not org:
        return ValidationResult(False, reason="Missing organization")
    if len(org) > 300:
        org = org[:300]

    # ── Required: link ────────────────────────────────────────────
    link = _clean_str(raw.get("link") or raw.get("url") or raw.get("application_url"))
    if not _is_valid_url(link):
        return ValidationResult(False, reason=f"Invalid URL: {link!r}")

    # ── Type ──────────────────────────────────────────────────────
    opp_type = _normalize_type(raw.get("type") or raw.get("opportunity_type"))
    if opp_type is None:
        opp_type = "internship"  # safe default

    # ── Optional fields ───────────────────────────────────────────
    description = _clean_str(raw.get("description"))
    deadline    = _normalize_date(raw.get("deadline") or raw.get("date_posted"))
    location    = _normalize_location(raw.get("location") or raw.get("locations"))
    stipend     = _clean_str(raw.get("stipend") or raw.get("salary") or raw.get("compensation"))
    source      = _clean_str(raw.get("source")) or "unknown"
    scraped_at  = raw.get("scraped_at") or datetime.utcnow().isoformat()

    # ── Skills ────────────────────────────────────────────────────
    required_skills = _normalize_skills(raw.get("required_skills") or raw.get("skills") or [])

    # ── Eligibility ───────────────────────────────────────────────
    eligibility = raw.get("eligibility")
    if not isinstance(eligibility, dict):
        eligibility = {}

    clean = {
        "title":           title,
        "organization":    org,
        "type":            opp_type,
        "description":     description,
        "required_skills": required_skills,
        "eligibility":     eligibility,
        "deadline":        deadline,
        "location":        location,
        "stipend":         stipend,
        "link":            link,
        "source":          source,
        "scraped_at":      scraped_at,
    }
    return ValidationResult(True, data=clean)


def validate_batch(records: list[dict]) -> tuple[list[dict], int]:
    """
    Validate a list of raw records.
    Returns: (list of valid clean dicts, count of invalid records)
    """
    valid_records = []
    invalid_count = 0
    for rec in records:
        result = validate(rec)
        if result.valid:
            valid_records.append(result.data)
        else:
            logger.debug(f"Invalid record — {result.reason}: {str(rec)[:80]}")
            invalid_count += 1
    return valid_records, invalid_count
