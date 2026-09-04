"""
backend/app/services/scraper.py
Phase 2 change: fetch_real_opportunities() now calls real scraper
instead of Groq LLM. load_local_opportunities() unchanged.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


async def fetch_real_opportunities() -> list:
    """
    BEFORE: called Groq to generate fake opportunities.
    NOW:    runs SimplifyJobsScraper for real listings.
    Returns list of dicts — same shape as before.
    main.py needs zero changes.
    """
    try:
        from app.database.connection import SessionLocal
        from app.database.models import OpportunityTable
        from app.scrapers.simplifyjobs import SimplifyJobsScraper
        from app.services.opportunity_repository import save_opportunities

        logger.info("[scraper] Running SimplifyJobs scraper...")
        scraper = SimplifyJobsScraper()
        run_result = scraper.run()

        if run_result["opportunities"]:
            summary = save_opportunities(run_result["opportunities"])
            logger.info(
                f"[scraper] inserted={summary['inserted']} "
                f"dupes={summary['duplicates']} invalid={summary['invalid']}"
            )

        db = SessionLocal()
        try:
            rows = (
                db.query(OpportunityTable)
                .filter(OpportunityTable.is_active == 1)
                .order_by(OpportunityTable.created_at.desc())
                .limit(500)
                .all()
            )
            return [row.to_dict() for row in rows]
        finally:
            db.close()

    except Exception as e:
        logger.error(f"[scraper] fetch_real_opportunities failed: {e}")
        return []


def load_local_opportunities() -> list:
    """UNCHANGED — loads sample_opportunities.json as fallback."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(base_dir, "../../data/sample_opportunities.json"))
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[scraper] Could not load local opportunities: {e}")
        return []
