"""
database/models.py
SQLAlchemy ORM table definitions.
These exist ALONGSIDE existing Pydantic models in app/models/ — NOT replacements.
Pydantic models  = API request/response shapes (unchanged)
SQLAlchemy models = real database table structure (new)
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


def _now():
    return datetime.now(timezone.utc)


class UserTable(Base):
    """
    Replaces: services/auth.py → users_db = {}
    All fields from the old dict are preserved with identical names.
    New fields are all nullable so existing data still works.
    """
    __tablename__ = "users"

    id       = Column(String(36),  primary_key=True)
    name     = Column(String(200), nullable=False)
    email    = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    branch   = Column(String(50),  nullable=False)
    year     = Column(Integer,     nullable=False)
    skills   = Column(Text,        nullable=False, default="[]")  # JSON string
    cgpa     = Column(Float,       nullable=True)

    # Profile extensions (all nullable)
    college      = Column(String(300), nullable=True)
    city         = Column(String(100), nullable=True)
    resume_url   = Column(Text,        nullable=True)
    linkedin_url = Column(Text,        nullable=True)
    github_url   = Column(Text,        nullable=True)

    # Notification preferences (Phase 3/4-era global toggle)
    match_threshold     = Column(Integer, nullable=False, default=50)
    email_notifications = Column(Integer, nullable=False, default=1)

    # Phase 8: admin role. Default 0 — nobody is admin unless explicitly
    # promoted (see migrations.py / Phase 8 report for how to grant this
    # safely; never hardcoded in source).
    is_admin = Column(Integer, nullable=False, default=0)

    # Phase 6: granular per-category in-app notification preferences.
    # All nullable-safe via default=1 (opt-out model) so existing users
    # keep receiving notifications unless they explicitly disable a category.
    notify_internship  = Column(Integer, nullable=False, default=1)
    notify_job         = Column(Integer, nullable=False, default=1)
    notify_hackathon   = Column(Integer, nullable=False, default=1)
    notify_scholarship = Column(Integer, nullable=False, default=1)
    notify_research    = Column(Integer, nullable=False, default=1)
    notify_remote_only = Column(Integer, nullable=False, default=0)

    # Phase 6: optional profile preferences consumed by the weighted match
    # engine (Preferred Role / Location / Remote components). No profile UI
    # exists yet to collect these (out of scope per Phase 6 rules — backend
    # support only) — until then these stay NULL for every user, and
    # match_engine.py treats NULL as "no preference" (neutral score),
    # never guessing or fabricating a preference the student never gave.
    preferred_role     = Column(String(200), nullable=True)
    preferred_location = Column(String(200), nullable=True)
    remote_preference  = Column(String(20),  nullable=True)  # "remote" | "onsite" | "hybrid"

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    # Relationships
    saved_opportunities = relationship(
        "SavedOpportunityTable",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    notifications = relationship(
        "NotificationTable",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<UserTable id={self.id} email={self.email}>"


class OpportunityTable(Base):
    """
    Replaces: data/sample_opportunities.json
    All 11 existing JSON fields preserved with identical names.
    New fields added for automation (source, content_hash, is_active, etc.)
    """
    __tablename__ = "opportunities"

    id           = Column(String(36),  primary_key=True)
    title        = Column(String(500), nullable=False)
    organization = Column(String(300), nullable=False)
    type         = Column(String(50),  nullable=False)
    description  = Column(Text,        nullable=True)
    required_skills = Column(Text, nullable=False, default="[]")  # JSON string
    eligibility     = Column(Text, nullable=False, default="{}")  # JSON string
    deadline     = Column(String(20),  nullable=True)
    location     = Column(String(200), nullable=True)
    stipend      = Column(String(200), nullable=True)
    link         = Column(Text,        nullable=False)

    # Automation fields
    source          = Column(String(50),  nullable=True, default="manual")
    content_hash    = Column(String(64),  nullable=True, unique=True)
    # Normalized (query-string-stripped, lowercased host) form of `link`,
    # used only for URL-based dedup matching — see deduplicator.py. Kept
    # separate from `link` itself so the real Apply-button URL is never
    # altered. Populated at insert time and backfilled for pre-existing
    # rows; NULL only for a row whose link failed to normalize.
    normalized_link = Column(Text,        nullable=True)
    is_active       = Column(Integer,     nullable=False, default=1)
    last_scraped_at = Column(DateTime,    nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)

    # Relationships
    saved_by = relationship(
        "SavedOpportunityTable",
        back_populates="opportunity",
        cascade="all, delete-orphan"
    )
    notifications = relationship(
        "NotificationTable",
        back_populates="opportunity",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_opps_type_active", "type", "is_active"),
        Index("idx_opps_deadline",    "deadline", "is_active"),
        Index("idx_opps_source",      "source"),
        Index("idx_opps_created_at",  "created_at"),
        Index("idx_opps_normalized_link", "normalized_link"),
    )

    def to_dict(self) -> dict:
        """
        Convert ORM row → same dict shape as the old JSON file.
        Called by routes/matching.py so the TF-IDF matcher works unchanged.
        """
        import json
        return {
            "id":               self.id,
            "title":            self.title,
            "organization":     self.organization,
            "type":             self.type,
            "description":      self.description or "",
            "required_skills":  json.loads(self.required_skills or "[]"),
            "eligibility":      json.loads(self.eligibility or "{}"),
            "deadline":         self.deadline,
            "location":         self.location,
            "stipend":          self.stipend,
            "link":             self.link,
            "source":           self.source,
            "is_active":        self.is_active,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<OpportunityTable id={self.id} title={self.title[:40]}>"


class SavedOpportunityTable(Base):
    """
    Replaces: browser localStorage (useSaved.js)
    Persistent, cross-device saved opportunities.
    """
    __tablename__ = "saved_opportunities"

    id             = Column(String(36), primary_key=True)
    user_id        = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False)
    saved_at       = Column(DateTime, nullable=False, default=_now)
    notes          = Column(Text, nullable=True)

    user        = relationship("UserTable",        back_populates="saved_opportunities")
    opportunity = relationship("OpportunityTable", back_populates="saved_by")

    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_saved_user_opp"),
        Index("idx_saved_user", "user_id"),
    )


class NotificationTable(Base):
    """
    New table. Powers the bell icon in TopNavbar with real notifications.
    """
    __tablename__ = "notifications"

    id             = Column(String(36), primary_key=True)
    user_id        = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=True)
    type           = Column(String(50),  nullable=False, default="new_match")
    title          = Column(String(300), nullable=False)
    message        = Column(Text,        nullable=False)
    match_score    = Column(Integer,     nullable=True)  # Phase 6: score that triggered this notification
    is_read        = Column(Integer,     nullable=False, default=0)
    created_at     = Column(DateTime,    nullable=False, default=_now)

    user        = relationship("UserTable",        back_populates="notifications")
    opportunity = relationship("OpportunityTable", back_populates="notifications")

    __table_args__ = (
        Index("idx_notif_user_unread", "user_id", "is_read", "created_at"),
    )


class EmailHistoryTable(Base):
    """
    New table (Phase 7). Records every email attempt — sent, failed, or
    skipped — so the system can prevent duplicate sends and support
    bounded retries of failed attempts. No relationships defined (kept
    simple, like ScraperLogTable) — queried directly by user_id/opportunity_id.
    """
    __tablename__ = "email_history"

    id                  = Column(String(36),  primary_key=True)
    user_id             = Column(String(36),  ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    opportunity_id      = Column(String(36),  ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=True)
    notification_id     = Column(String(36),  ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True)
    recipient_email     = Column(String(255), nullable=False)
    email_type          = Column(String(50),  nullable=False, default="opportunity_match")
    subject             = Column(String(300), nullable=False)
    status              = Column(String(20),  nullable=False, default="pending")  # pending|sent|failed|skipped
    error_message       = Column(Text,        nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    retry_count         = Column(Integer,     nullable=False, default=0)
    sent_at             = Column(DateTime,    nullable=True)
    created_at          = Column(DateTime,    nullable=False, default=_now)

    __table_args__ = (
        Index("idx_email_history_dedup", "user_id", "opportunity_id", "email_type", "status"),
    )


class ScraperLogTable(Base):
    """
    New table. Tracks every scraper execution for monitoring.
    """
    __tablename__ = "scraper_logs"

    id                 = Column(String(36),  primary_key=True)
    source             = Column(String(100), nullable=False)
    status             = Column(String(20),  nullable=False, default="running")
    total_found        = Column(Integer,     nullable=False, default=0)
    inserted           = Column(Integer,     nullable=False, default=0)
    updated            = Column(Integer,     nullable=False, default=0)
    duplicates_skipped = Column(Integer,     nullable=False, default=0)
    errors             = Column(Integer,     nullable=False, default=0)
    error_details      = Column(Text,        nullable=True)
    started_at         = Column(DateTime,    nullable=False, default=_now)
    finished_at        = Column(DateTime,    nullable=True)
    duration_ms        = Column(Integer,     nullable=True)

    __table_args__ = (
        Index("idx_scraper_source_ran", "source", "started_at"),
    )
