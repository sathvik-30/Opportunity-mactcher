"""
backend/app/services/notification_service.py — Phase 6
─────────────────────────────────────────────────────────────────
Automatic notification pipeline. Evaluates newly-inserted
opportunities against every registered student and creates an
in-app notification for each student who is eligible, clears the
configurable match threshold, has that category enabled in their
preferences, and hasn't already been notified about this exact
opportunity.

Reuses, does NOT duplicate:
  - match_engine.evaluate_match()  (Phase 6, weighted scoring)
  - NotificationTable / UserTable  (already existed / extended in-place)
  - SessionLocal                   (existing DB session factory)

Entry points:
  match_new_opportunities(opportunity_dicts) — PREFERRED. Evaluates a
    whole batch of newly-inserted opportunities using a SINGLE
    `db.query(UserTable).all()` for the entire batch, instead of one
    per opportunity. Called from
    opportunity_repository.save_opportunities() once per scrape run
    (see that file for the integration point) — a single scrape can
    insert up to ~500 opportunities, and re-querying the full `users`
    table that many times was a real scalability problem as the user
    base grows: it turns N redundant full-table scans into exactly 1.

  match_new_opportunity(opportunity_dict) — single-opportunity form,
    kept for callers evaluating just one (e.g. tests). Internally just
    calls match_new_opportunities() with a one-item list.

Both fire for every insertion path (scheduled scraper runs, manual
admin trigger, any future scraper) without touching the scheduler
itself.
─────────────────────────────────────────────────────────────────
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from app.config import (
    EMAIL_BATCH_SIZE,
    EMAIL_DELAY_SECONDS,
    EMAIL_MAX_RETRIES,
    FRONTEND_URL,
    MATCH_THRESHOLD,
)
from app.database.connection import SessionLocal
from app.database.models import EmailHistoryTable, NotificationTable, UserTable
from app.services.email_service import send_email
from app.services.email_templates import generate_opportunity_email
from app.services.match_engine import evaluate_match

logger = logging.getLogger(__name__)

_TYPE_EMOJI = {
    "internship":  "🔔",
    "job":         "💼",
    "hackathon":   "🚀",
    "scholarship": "🎓",
    "research":    "🔬",
}

# Maps an opportunity type to the per-category preference column on UserTable.
# Types not in this map (e.g. a future category) are never silently
# suppressed — see _user_wants_notification below.
_PREF_COLUMN = {
    "internship":  "notify_internship",
    "job":         "notify_job",
    "hackathon":   "notify_hackathon",
    "scholarship": "notify_scholarship",
    "research":    "notify_research",
}


def _user_to_student_dict(user: UserTable) -> dict:
    """Same shape match_engine.evaluate_match() expects."""
    skills = user.skills
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except Exception:
            skills = [s.strip() for s in skills.split(",") if s.strip()]
    return {
        "id":                 user.id,
        "name":               user.name,
        "branch":             user.branch,
        "year":               user.year,
        "skills":             skills or [],
        "cgpa":               user.cgpa,
        "preferred_role":     getattr(user, "preferred_role", None),
        "preferred_location": getattr(user, "preferred_location", None),
        "remote_preference":  getattr(user, "remote_preference", None),
    }


def _user_wants_notification(user: UserTable, opportunity_type: str) -> bool:
    """
    Step 16 — per-category preferences. Defaults to True (opt-out model):
    a user only stops getting notified for a category if they've
    explicitly disabled it. Unknown/future opportunity types are never
    silently suppressed just because no preference column exists for them.
    """
    col_name = _PREF_COLUMN.get(opportunity_type)
    if col_name is None:
        return True
    return bool(getattr(user, col_name, 1))


def _build_message(opportunity: dict, score: int) -> tuple[str, str]:
    """
    Rule-based, no LLM. Returns (title, message) ready to store/display.
    """
    opp_type = (opportunity.get("type") or "opportunity")
    emoji = _TYPE_EMOJI.get(opp_type, "🔔")
    title = f"{emoji} New {opp_type.title()} Match"

    deadline = opportunity.get("deadline")
    lines = [
        opportunity.get("title") or "New opportunity",
        f"{score}% Match",
    ]
    if deadline:
        lines.append(f"Deadline: {deadline}")
    lines.append("Click to view.")
    message = "\n".join(lines)

    return title, message


def _maybe_send_email(db, user: UserTable, opportunity: dict, match_result: dict, notification_id: str) -> str:
    """
    Phase 7 — the email side of the pipeline. Reuses the SAME match_result
    already computed for the in-app notification (no second matching pass).

    Returns one of: "sent", "skipped_pref", "skipped_duplicate",
    "skipped_gave_up", "failed". Never raises — a failed/skipped email must
    never break the notification pipeline or the scraper that triggered it.
    """
    email_type = "opportunity_match"

    # Step 13/14 — reuse the existing preference columns. No second
    # preference system. email_notifications is the master email toggle;
    # the per-category gate already happened one level up in
    # match_new_opportunity() via _user_wants_notification().
    if not getattr(user, "email_notifications", 1):
        return "skipped_pref"
    if not user.email:
        return "skipped_pref"

    # Step 9 — duplicate prevention: never re-send an email that already
    # succeeded for this exact user + opportunity + email_type.
    already_sent = (
        db.query(EmailHistoryTable)
        .filter(
            EmailHistoryTable.user_id == user.id,
            EmailHistoryTable.opportunity_id == opportunity.get("id"),
            EmailHistoryTable.email_type == email_type,
            EmailHistoryTable.status == "sent",
        )
        .first()
    )
    if already_sent:
        return "skipped_duplicate"

    # Step 10 — bounded retries for previously-failed attempts.
    failed_attempts = (
        db.query(EmailHistoryTable)
        .filter(
            EmailHistoryTable.user_id == user.id,
            EmailHistoryTable.opportunity_id == opportunity.get("id"),
            EmailHistoryTable.email_type == email_type,
            EmailHistoryTable.status == "failed",
        )
        .count()
    )
    if failed_attempts >= EMAIL_MAX_RETRIES:
        return "skipped_gave_up"

    subject, html_body = generate_opportunity_email(
        student_name=user.name,
        opportunity=opportunity,
        match_result=match_result,
        frontend_url=FRONTEND_URL,
    )

    result = send_email(user.email, subject, html_body)

    history = EmailHistoryTable(
        id=str(uuid.uuid4()),
        user_id=user.id,
        opportunity_id=opportunity.get("id"),
        notification_id=notification_id,
        recipient_email=user.email,
        email_type=email_type,
        subject=subject,
        retry_count=failed_attempts,
        created_at=datetime.now(timezone.utc),
    )

    if result["status"] == "sent":
        history.status = "sent"
        history.sent_at = datetime.now(timezone.utc)
    elif result["status"] == "skipped":
        history.status = "skipped"
        history.error_message = result.get("reason")
    else:
        history.status = "failed"
        history.error_message = result.get("reason")

    try:
        db.add(history)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"[email] could not record EmailHistory for user {user.id}: {e}")

    return history.status


def _match_one_opportunity(db, students: list, opportunity: dict, threshold: int) -> dict:
    """
    Evaluate `opportunity` against an ALREADY-LOADED `students` list and
    create notifications for those who qualify. Does not open a session or
    query users itself — callers (match_new_opportunities /
    match_new_opportunity below) own that, so a batch of opportunities can
    share one query instead of re-fetching the full `users` table per
    opportunity.

    Returns a summary dict (same shape as before this was extracted):
      {
        "opportunity_id": "...",
        "evaluated": N,
        "notified": M,
        "skipped_ineligible": X,
        "skipped_below_threshold": Y,
        "skipped_duplicate": Z,
        "skipped_preference": W,
      }
    """
    summary = {
        "opportunity_id": opportunity.get("id"),
        "evaluated": 0,
        "notified": 0,
        "skipped_ineligible": 0,
        "skipped_below_threshold": 0,
        "skipped_duplicate": 0,
        "skipped_preference": 0,
        "emails_sent": 0,
        "emails_failed": 0,
        "emails_skipped": 0,
    }

    opp_type = opportunity.get("type")

    for user in students:
        summary["evaluated"] += 1

        if not _user_wants_notification(user, opp_type):
            summary["skipped_preference"] += 1
            continue

        student_dict = _user_to_student_dict(user)
        result = evaluate_match(student_dict, opportunity)

        if not result["eligible"]:
            summary["skipped_ineligible"] += 1
            continue
        if result["score"] < threshold:
            summary["skipped_below_threshold"] += 1
            continue

        # Step 17 — duplicate prevention for the IN-APP notification:
        # same user + same opportunity already notified → don't create
        # a second notification row. This is a SEPARATE concern from
        # email dedup (Step 9), which has its own check inside
        # _maybe_send_email() based on EmailHistory — so a notification
        # that already exists must NOT short-circuit a legitimate email
        # retry for a previously-FAILED send. Without this split, a
        # failed email could never actually be retried on a later run.
        existing_notif = (
            db.query(NotificationTable)
            .filter(
                NotificationTable.user_id == user.id,
                NotificationTable.opportunity_id == opportunity.get("id"),
            )
            .first()
        )

        if existing_notif:
            summary["skipped_duplicate"] += 1
            notif_id = existing_notif.id
        else:
            title, message = _build_message(opportunity, result["score"])
            notif = NotificationTable(
                id=str(uuid.uuid4()),
                user_id=user.id,
                opportunity_id=opportunity.get("id"),
                type=opp_type or "new_match",
                title=title,
                message=message,
                match_score=result["score"],
                is_read=0,
                created_at=datetime.now(timezone.utc),
            )
            try:
                db.add(notif)
                db.commit()
                summary["notified"] += 1
                notif_id = notif.id
            except Exception as e:
                db.rollback()
                logger.warning(f"[notify] could not create notification for user {user.id}: {e}")
                continue

        # Step 11 — email step of the SAME pipeline, reusing the SAME
        # match result. Runs whether the notification was just created
        # or already existed — its own dedup (EmailHistory status=sent)
        # and retry cap (EMAIL_MAX_RETRIES) decide whether to actually
        # attempt a send, so failed sends CAN be retried on a later run.
        email_status = _maybe_send_email(db, user, opportunity, result, notif_id)
        if email_status == "sent":
            summary["emails_sent"] += 1
            # Step 19/20 — soft rate limit: pause briefly every
            # EMAIL_BATCH_SIZE sends so we never hammer the SMTP
            # provider in one tight loop. Synchronous by design for
            # now (documented limitation — see notification_service
            # module docstring / Phase 7 report).
            if summary["emails_sent"] % EMAIL_BATCH_SIZE == 0:
                time.sleep(EMAIL_DELAY_SECONDS)
        elif email_status == "failed":
            summary["emails_failed"] += 1
        else:
            summary["emails_skipped"] += 1

    logger.info(
        f"[notify] opportunity={summary['opportunity_id']} "
        f"evaluated={summary['evaluated']} notified={summary['notified']} "
        f"below_threshold={summary['skipped_below_threshold']} "
        f"ineligible={summary['skipped_ineligible']} "
        f"duplicate={summary['skipped_duplicate']} "
        f"preference_opt_out={summary['skipped_preference']} "
        f"emails_sent={summary['emails_sent']} "
        f"emails_failed={summary['emails_failed']} "
        f"emails_skipped={summary['emails_skipped']}"
    )
    return summary


def match_new_opportunities(opportunities: list[dict], threshold: int | None = None) -> list[dict]:
    """
    PREFERRED entry point for anything processing more than one
    opportunity (i.e. every real scrape run). Evaluates the whole batch
    against every registered student using a SINGLE
    `db.query(UserTable).all()` for the entire batch, instead of once per
    opportunity — the fix for a real scalability problem: a single scrape
    can insert up to ~500 opportunities, and re-running a full-table scan
    of `users` that many times (previously once per opportunity, inside
    what is now _match_one_opportunity) got more expensive as the user
    base grows. This does the exact same amount of match-evaluation work
    (every user still gets checked against every new opportunity — that's
    inherent to the feature, not avoidable without changing its behavior)
    while cutting N redundant full-table queries down to 1 per batch.

    opportunities: list of dicts, e.g. [OpportunityTable.to_dict(), ...].
    threshold:      override MATCH_THRESHOLD for this call (mainly for tests).

    Returns a list of per-opportunity summary dicts, same shape
    match_new_opportunity() used to return for a single call.
    """
    if not opportunities:
        return []

    threshold = MATCH_THRESHOLD if threshold is None else threshold

    # expire_on_commit=False, scoped to just this session (SessionLocal's
    # app-wide default is untouched): SQLAlchemy's default behavior expires
    # every loaded ORM object after each db.commit(), so the NEXT attribute
    # access on any of the cached `students` re-triggers an individual
    # single-row SELECT — and this loop commits once per notification and
    # once per email-history row. Without this override, the one intended
    # `.all()` scan below stays a single query, but it gets shadowed by many
    # small per-row refetches, undermining the whole point of caching
    # `students` for the batch. Safe here: this function only reads `user`
    # rows, never writes to them, and the two objects it does create and
    # commit (NotificationTable/EmailHistoryTable rows) use client-generated
    # UUIDs, not server-generated values, so nothing needs a post-commit
    # refresh to be read correctly.
    db = SessionLocal(expire_on_commit=False)
    try:
        students = db.query(UserTable).all()  # <-- loaded ONCE for the whole batch
        return [
            _match_one_opportunity(db, students, opportunity, threshold)
            for opportunity in opportunities
        ]
    finally:
        db.close()


def match_new_opportunity(opportunity: dict, threshold: int | None = None) -> dict:
    """
    Single-opportunity form of match_new_opportunities() — kept for
    callers evaluating just one opportunity (e.g. tests). Prefer
    match_new_opportunities() when processing more than one, since each
    call here still opens its own session and queries the full `users`
    table.
    """
    return match_new_opportunities([opportunity], threshold=threshold)[0]
