"""
backend/app/scrapers/base.py
─────────────────────────────────────────────────────────────────
Abstract base class for all opportunity scrapers.
─────────────────────────────────────────────────────────────────
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "OpportunityMatcher/2.0 (educational project)",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

VALID_TYPES = {
    "internship", "job", "hackathon", "scholarship",
    "fellowship", "research", "competition", "open_source",
}


class BaseScraper(ABC):
    """
    Abstract base class. All scrapers inherit from this.
    Subclasses must implement: fetch(), parse(), normalize().
    run() orchestrates the full pipeline safely.
    """

    source_name: str = "base"
    base_url: str = ""
    timeout: int = 20

    def __init__(self):
        self._client = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers=DEFAULT_HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    def _close_client(self):
        if self._client and not self._client.is_closed:
            self._client.close()
            self._client = None

    def fetch_url(self, url: str, **kwargs) -> httpx.Response:
        """Fetch a URL with shared client. Raises on HTTP errors."""
        response = self._get_client().get(url, **kwargs)
        response.raise_for_status()
        return response

    @abstractmethod
    def fetch(self) -> Any:
        """Retrieve raw data from the source. Raise on failure."""

    @abstractmethod
    def parse(self, raw: Any) -> list:
        """Convert raw source data → list of raw record dicts."""

    @abstractmethod
    def normalize(self, record: dict) -> dict | None:
        """
        Convert one raw record → standard opportunity dict.
        Return None if the record is unusable.
        Never invent missing data.

        Required keys in returned dict:
          title, organization, type, link, source, scraped_at
        Optional keys:
          description, required_skills, eligibility,
          deadline, location, stipend
        """

    def run(self) -> dict:
        """
        Full pipeline: fetch → parse → normalize.
        Returns summary dict with 'opportunities' list.
        One bad record never crashes the run.
        """
        start = time.time()
        logger.info(f"[{self.source_name}] Starting scrape of {self.base_url}")

        result = {
            "source": self.source_name,
            "fetched": 0,
            "normalized": 0,
            "failed": 0,
            "opportunities": [],
        }

        # Fetch
        try:
            raw = self.fetch()
        except httpx.TimeoutException:
            logger.error(f"[{self.source_name}] Timeout")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"[{self.source_name}] HTTP {e.response.status_code}")
            return result
        except httpx.RequestError as e:
            logger.error(f"[{self.source_name}] Connection error: {e}")
            return result
        except Exception as e:
            logger.error(f"[{self.source_name}] Fetch error: {e}")
            return result

        # Parse
        try:
            records = self.parse(raw)
            result["fetched"] = len(records)
            logger.info(f"[{self.source_name}] Parsed {len(records)} records")
        except Exception as e:
            logger.error(f"[{self.source_name}] Parse error: {e}")
            return result

        # Normalize each record individually
        for i, record in enumerate(records):
            try:
                normalized = self.normalize(record)
                if normalized is not None:
                    result["opportunities"].append(normalized)
                    result["normalized"] += 1
                else:
                    result["failed"] += 1
            except Exception as e:
                logger.warning(f"[{self.source_name}] Record {i} failed: {e}")
                result["failed"] += 1

        elapsed = round(time.time() - start, 2)
        logger.info(
            f"[{self.source_name}] Done in {elapsed}s — "
            f"fetched={result['fetched']} ok={result['normalized']} failed={result['failed']}"
        )
        self._close_client()
        return result
