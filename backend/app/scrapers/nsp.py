"""
backend/app/scrapers/nsp.py
─────────────────────────────────────────────────────────────────
SOURCE:  National Scholarship Portal (NSP)
         https://scholarships.gov.in/All-Scholarships

DATA:    Government of India (Ministry of Electronics & IT) public
         "Schemes on NSP" listing page. Server-rendered HTML,
         no login, no CAPTCHA, no JavaScript rendering required.
         Every scheme card includes: ministry/department, scheme
         name, application window dates, and links to the official
         PDF "Specifications" (and often "FAQ") documents.

WHY THIS SOURCE:
  - Public government transparency page — no authentication wall
  - Server-rendered HTML (confirmed via direct fetch: the scheme
    list is present in the initial page response, not loaded by
    client-side JS)
  - Every scheme links to a genuine, scheme-specific government
    PDF ("Specifications") — used as the record's `link` field
  - No CAPTCHA, no anti-bot measures observed
  - Real dates are provided per scheme ("Student Application Open
    till : DD-MM-YYYY", or "NOT YET OPENED" when not yet decided)

IMPORTANT — SOURCE VALIDATION NOTES (see Phase 4 report):
  - This scraper only covers the "Central Sector Schemes" tab,
    which is what the page returns by default on a plain GET.
    "Centrally Sponsored Schemes" and "State Schemes" tabs are
    populated by additional in-page requests that were not
    enumerated as part of this scraper. Documented as a known
    limitation rather than guessed at.
  - Detailed eligibility criteria, scholarship amounts, and a
    scheme-specific "apply" URL are NOT present on the listing
    page (they live inside the linked PDF documents / behind
    the OTR-login application flow). We do NOT fabricate these —
    they are left as None / {} / [].
  - We use the scheme's "Specifications" PDF URL as the record's
    `link`, since it's the only genuine, scheme-specific public
    URL available on the listing page. This also avoids false
    dedup collisions that would occur if every scheme reused the
    same generic "Apply" URL.
  - Ministry/organization is read from the Bootstrap accordion
    button text (`.accordion-item > .accordion-header button`),
    confirmed against a live fetch of the page. The per-scheme
    "by Ministry X" label that used to exist is HTML-commented
    out in the current markup, so it is not a usable source.
  - Selectors are scoped per accordion-item / per scheme row (not
    global forward/backward DOM walks), so a scheme's fields can
    never leak into a neighboring scheme or ministry. If NSP
    changes its markup, affected records are simply skipped
    (never fabricated), and the run still reports accurate
    fetched/failed counts.
─────────────────────────────────────────────────────────────────
"""

import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Matches "Student Application Open till : 31-10-2026" or
# "Student Application Open till (for Renewal): 30-09-2026"
_DEADLINE_RE = re.compile(
    r"Student Application(?:\s*\(for Renewal\))?\s*(?:Open till)?\s*:\s*"
    r"(\d{2}-\d{2}-\d{4}|NOT YET OPENED)",
    re.IGNORECASE,
)

# Matches "Scheme Open from : 01-06-2026" (used only as a fallback
# reference date — NEVER used as a deadline)
_OPEN_FROM_RE = re.compile(
    r"Scheme Open from(?:\s*\(for Renewal\))?\s*:\s*(\d{2}-\d{2}-\d{4}|NOT YET OPENED)",
    re.IGNORECASE,
)


class NSPScraper(BaseScraper):
    """
    Scrapes real scholarship scheme listings from the Government of
    India's National Scholarship Portal "Schemes on NSP" page.

    Data source:
      https://scholarships.gov.in/All-Scholarships

    Every record contains a genuine ministry/department name, scheme
    name, real application-window dates (when published), and a
    genuine government PDF URL.
    """

    source_name = "nsp"
    base_url = "https://scholarships.gov.in/All-Scholarships"
    timeout = 30

    # Safety cap — this listing page is not expected to exceed a few
    # hundred schemes, but cap defensively like the existing scraper.
    MAX_RECORDS = 300

    def fetch(self) -> str:
        """Download the public 'Schemes on NSP' HTML page."""
        logger.info(f"[{self.source_name}] Fetching {self.base_url}")
        response = self.fetch_url(self.base_url)
        return response.text

    def parse(self, raw: str) -> list:
        """
        Parse the scheme-listing HTML into a list of raw record dicts.

        CONFIRMED real markup (verified via live fetch on 2026-08-20,
        not guessed at — see debug_nsp_structure2.py output):

          <div class="accordion-item">
            <h7 class="accordion-header">
              <button class="accordion-button">Ministry of Home Affairs</button>
            </h7>
            <div class="accordion-collapse ...">
              <div class="accordion-body">
                <div class="row mb-4 border-1 border-bottom">   <!-- one scheme -->
                  <div class="col-md-2"><img src="...MinistryImages/....png"/></div>
                  <div class="col-md-10">
                    <h6>Scheme Name (Merit Based Scheme)</h6>
                    <span class="...">Scheme Open from : DD-MM-YYYY</span>
                    <span class="...">Student Application Open till : DD-MM-YYYY</span>
                    ...
                    <a href="....pdf">Specifications</a>
                    <a href="....pdf">FAQ</a>
                  </div>
                </div>
                <div class="row mb-4 border-1 border-bottom"> ... next scheme ... </div>
              </div>
            </div>
          </div>

        The ministry name used to also be printed as a per-scheme
        <h6>by Ministry X</h6>, but that line is HTML-commented out
        in the live markup — the accordion button text is the only
        genuinely visible source for it, so we read it from there,
        scoped per accordion-item (never inherited across ministries
        by accident).
        """
        soup = BeautifulSoup(raw, "lxml")
        records = []

        accordion_items = soup.find_all("div", class_="accordion-item")
        logger.info(f"[{self.source_name}] Found {len(accordion_items)} ministry groups")

        for item in accordion_items:
            button = item.find("button", class_="accordion-button")
            ministry = button.get_text(strip=True) if button else None
            if not ministry:
                # No genuine ministry name available for this group — skip
                # its schemes rather than fabricating an organization.
                continue

            scheme_rows = item.find_all("div", class_="row mb-4 border-1 border-bottom")
            for row in scheme_rows:
                heading = row.find("h6")
                if not heading:
                    continue
                scheme_name = heading.get_text(strip=True)

                # Metadata: the application-window spans live inside this row only.
                spans = row.find_all("span")
                meta_text = " ".join(s.get_text(" ", strip=True) for s in spans)

                # Links: scoped to this row only (never leaks into the next scheme).
                spec_url = None
                for link in row.find_all("a"):
                    href = link.get("href", "")
                    label = link.get_text(strip=True).lower()
                    if href and "specification" in label:
                        spec_url = href
                        break
                if not spec_url:
                    for link in row.find_all("a"):
                        href = link.get("href", "")
                        if href.lower().endswith(".pdf"):
                            spec_url = href
                            break

                records.append({
                    "scheme_name": scheme_name,
                    "ministry": ministry,
                    "meta_text": meta_text,
                    "spec_url": spec_url,
                })

        return records[: self.MAX_RECORDS]

    def normalize(self, record: dict) -> dict | None:
        """
        Convert one NSP raw record → standard opportunity dict.

        Fields we USE (genuinely from source):
          scheme_name → title
          ministry    → organization
          spec_url    → link
          meta_text   → deadline (parsed)

        Fields we do NOT fabricate:
          stipend      → None (amount not on listing page)
          eligibility  → {}   (detailed criteria live in the PDF)
          location     → None (not structured on this tab)
          required_skills → [] (not applicable to scholarships)
        """
        title = (record.get("scheme_name") or "").strip()
        organization = (record.get("ministry") or "").strip()
        spec_url = (record.get("spec_url") or "").strip()
        meta_text = record.get("meta_text") or ""

        if not title or not organization or not spec_url:
            return None
        if not spec_url.startswith("http"):
            return None

        # ── Deadline: parse "DD-MM-YYYY" → "YYYY-MM-DD".
        # "NOT YET OPENED" or no match → None (never invented).
        deadline = None
        m = _DEADLINE_RE.search(meta_text)
        if m and m.group(1).upper() != "NOT YET OPENED":
            try:
                dt = datetime.strptime(m.group(1), "%d-%m-%Y")
                deadline = dt.strftime("%Y-%m-%d")
            except ValueError:
                deadline = None

        # Reference "open from" date — used only in the description,
        # never as a deadline.
        open_from = None
        m2 = _OPEN_FROM_RE.search(meta_text)
        if m2 and m2.group(1).upper() != "NOT YET OPENED":
            open_from = m2.group(1)

        # Description assembled only from real, extracted fields.
        parts = [f"{title} — offered by {organization}."]
        if open_from:
            parts.append(f"Applications open from {open_from}.")
        if deadline:
            parts.append(f"Application deadline: {deadline}.")
        elif "NOT YET OPENED" in meta_text.upper():
            parts.append("Application window not yet opened for this cycle.")
        description = " ".join(parts)

        scraped_at = datetime.now(timezone.utc).isoformat()

        return {
            "title":           title,
            "organization":    organization,
            "type":            "scholarship",
            "description":     description,
            "required_skills": [],
            "eligibility":     {},   # not available on the listing page
            "deadline":        deadline,
            "location":        None,  # not structured on this tab
            "stipend":         None,  # not on the listing page
            "link":            spec_url,
            "source":          self.source_name,
            "scraped_at":      scraped_at,
        }


# ── Manual run entrypoint ─────────────────────────────────────────

if __name__ == "__main__":
    """
    Run manually to test the scraper without starting FastAPI.

    From the backend/ directory:
        python -m app.scrapers.nsp

    This will:
      1. Fetch real data from scholarships.gov.in
      2. Parse and normalize scheme records
      3. Validate each record
      4. Insert into SQLite (deduplicating)
      5. Print a summary
    """
    import sys
    import os
    import time

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s — %(message)s",
    )

    print("=" * 48)
    print("  Opportunity Scraper")
    print(f"  Source: NSP (scholarships.gov.in)")
    print(f"  URL: /All-Scholarships")
    print("=" * 48)

    start = time.time()

    scraper = NSPScraper()
    run_result = scraper.run()

    from app.services.opportunity_repository import save_opportunities
    from app.database.migrations import run_migrations

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
