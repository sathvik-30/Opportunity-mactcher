"""
backend/app/scrapers/simplifyjobs.py
─────────────────────────────────────────────────────────────────
SOURCE:  SimplifyJobs / Summer Internships
         https://github.com/SimplifyJobs/Summer2025-Internships

DATA:    Public JSON file updated daily by the Pitt CSC community
         and SimplifyJobs. Contains real internship listings from
         actual company career pages.

WHY THIS SOURCE:
  - Publicly available on GitHub (raw.githubusercontent.com is
    in the network allowlist)
  - Machine-readable JSON — no HTML parsing needed
  - Updated daily by a real community
  - Every record has a genuine company career page URL
  - No CAPTCHA, no login, no anti-bot measures
  - Fields: company_name, title, url, locations, category, active,
            date_posted, terms, degrees

IMPORTANT:
  - We only take ACTIVE listings (active=True)
  - We only take IS_VISIBLE listings
  - We do NOT invent any fields
  - Missing fields stay None
  - Deadlines: date_posted is used as a reference date only;
    no deadline is fabricated since the source doesn't provide one
─────────────────────────────────────────────────────────────────
"""

import json
import logging
import time
from datetime import datetime, timezone

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Mapping from SimplifyJobs categories → our canonical types
CATEGORY_TO_TYPE = {
    "software engineering": "internship",
    "software":             "internship",
    "hardware engineering": "internship",
    "hardware":             "internship",
    "ai/ml/data":           "internship",
    "data science, ai & machine learning": "internship",
    "quant":                "internship",
    "product":              "internship",
    "product management":   "internship",
    "cybersecurity":        "internship",
    "design":               "internship",
    "research":             "research",
    "finance":              "internship",
    "marketing":            "internship",
    "operations":           "internship",
}

# Skills inferred from category — ONLY where the category literally
# implies a technology. We do not fabricate skills.
CATEGORY_TO_SKILLS = {
    "software engineering":  ["Software Engineering"],
    "software":              ["Software Development"],
    "hardware engineering":  ["Hardware Engineering"],
    "hardware":              ["Hardware"],
    "ai/ml/data":            ["Machine Learning", "Data Science"],
    "data science, ai & machine learning": ["Data Science", "Machine Learning"],
    "quant":                 ["Mathematics", "Statistics"],
    "cybersecurity":         ["Cybersecurity"],
    "research":              ["Research"],
    "product":               [],
    "product management":    [],
}


class SimplifyJobsScraper(BaseScraper):
    """
    Scrapes real internship listings from the community-maintained
    SimplifyJobs GitHub dataset.

    Data source:
      https://raw.githubusercontent.com/SimplifyJobs/
             Summer2025-Internships/dev/.github/scripts/listings.json

    This file is updated daily. Every record contains a genuine
    application URL pointing to the company's career page.
    """

    source_name = "simplifyjobs"
    base_url = (
        "https://raw.githubusercontent.com/"
        "SimplifyJobs/Summer2025-Internships/"
        "dev/.github/scripts/listings.json"
    )
    timeout = 30  # large JSON file

    # Limit per run to keep startup fast and avoid DB flooding
    MAX_RECORDS = 200

    def fetch(self) -> str:
        """Download the JSON file from GitHub raw."""
        logger.info(f"[{self.source_name}] Fetching {self.base_url}")
        response = self.fetch_url(self.base_url)
        return response.text

    def parse(self, raw: str) -> list:
        """
        Parse JSON → list of active, visible records.
        Filter: active=True AND is_visible=True.
        Cap at MAX_RECORDS to keep runs manageable.
        """
        all_records = json.loads(raw)
        active = [
            r for r in all_records
            if r.get("active") is True and r.get("is_visible") is True
        ]
        logger.info(
            f"[{self.source_name}] {len(all_records)} total, "
            f"{len(active)} active+visible, "
            f"capping at {self.MAX_RECORDS}"
        )
        return active[: self.MAX_RECORDS]

    def normalize(self, record: dict) -> dict | None:
        """
        Convert one SimplifyJobs record → standard opportunity dict.

        Fields we USE (genuinely from source):
          company_name → organization
          title        → title
          url          → link
          locations    → location
          category     → type + required_skills (implied only)
          date_posted  → scraped_at (NOT used as deadline)
          terms        → included in description

        Fields we do NOT fabricate:
          deadline     → None (source doesn't provide one)
          stipend      → None (source doesn't provide one)
          eligibility  → {} (source doesn't provide one)
          description  → constructed from available real fields only
        """
        # Extract real fields
        company  = record.get("company_name", "").strip()
        title    = record.get("title", "").strip()
        url      = record.get("url", "").strip()
        category = (record.get("category") or "").lower().strip()
        locations = record.get("locations") or []
        terms     = record.get("terms") or []

        # Skip records missing any required field
        if not company or not title or not url:
            return None
        if not url.startswith("http"):
            return None

        # Map category → opportunity type
        opp_type = CATEGORY_TO_TYPE.get(category, "internship")

        # Location: join list with separator
        location = " | ".join(loc for loc in locations if loc) or None

        # Description: assembled from REAL source fields only
        parts = []
        if title:
            parts.append(f"{title} at {company}.")
        if terms:
            parts.append(f"Term(s): {', '.join(terms)}.")
        if category:
            parts.append(f"Category: {category.title()}.")
        if locations:
            parts.append(f"Location(s): {', '.join(locations)}.")
        description = " ".join(parts) if parts else None

        # Skills: only from the category→skills map (these are broad
        # category-level tags, not fabricated specific skills)
        required_skills = CATEGORY_TO_SKILLS.get(category, [])

        # Scraped timestamp
        scraped_at = datetime.now(timezone.utc).isoformat()

        return {
            "title":           title,
            "organization":    company,
            "type":            opp_type,
            "description":     description,
            "required_skills": required_skills,
            "eligibility":     {},           # source doesn't provide this
            "deadline":        None,         # source doesn't provide this
            "location":        location,
            "stipend":         None,         # source doesn't provide this
            "link":            url,
            "source":          self.source_name,
            "scraped_at":      scraped_at,
        }


# ── Manual run entrypoint ─────────────────────────────────────────

if __name__ == "__main__":
    """
    Run manually to test the scraper without starting FastAPI.

    From the backend/ directory:
        python -m app.scrapers.simplifyjobs

    This will:
      1. Fetch real data from GitHub
      2. Parse and normalize up to 200 records
      3. Validate each record
      4. Insert into SQLite (deduplicating)
      5. Print a summary
    """
    import os
    import sys

    # Ensure the backend/ folder is in the Python path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

    # Initialize logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s — %(message)s",
    )

    print("=" * 48)
    print("  Opportunity Scraper")
    print("  Source: SimplifyJobs (GitHub)")
    print("  URL: Summer2025-Internships listings.json")
    print("=" * 48)

    start = time.time()

    # Run scraper
    scraper = SimplifyJobsScraper()
    run_result = scraper.run()

    # Persist via repository
    from app.database.migrations import run_migrations
    from app.services.opportunity_repository import save_opportunities

    print("  Initializing database...")
    run_migrations()

    print(f"  Persisting {len(run_result['opportunities'])} normalized records...")
    summary = save_opportunities(run_result["opportunities"])

    elapsed = round(time.time() - start, 1)

    print()
    print("=" * 48)
    print(f"  Fetched:    {run_result['fetched']}")
    print(f"  Normalized: {run_result['normalized']}")
    print(f"  Invalid:    {run_result['failed']}")
    print(f"  Inserted:   {summary['inserted']}")
    print(f"  Duplicates: {summary['duplicates']}")
    print(f"  Errors:     {summary['errors']}")
    print(f"  Duration:   {elapsed}s")
    print("=" * 48)
