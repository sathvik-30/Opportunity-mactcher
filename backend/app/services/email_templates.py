"""
backend/app/services/email_templates.py — Phase 7
─────────────────────────────────────────────────────────────────
Renders the opportunity-match HTML email. Kept separate from
email_service.py (which only handles SMTP transport) — matches the
Phase 7 spec's own separation of "Email Service" (Step 4) from
"Email Template" (Step 5).

generate_opportunity_email() is a pure function: given a student,
an opportunity, and a match result, it returns (subject, html) and
sends nothing. This is also what Step 25 ("email preview") uses —
call it directly to see the HTML without ever touching SMTP.

Content safety (Step 21):
  Every dynamic value (organization, title, description, skills,
  location) is html.escape()'d before insertion — company names,
  scraped titles, etc. are treated as untrusted input.

URL safety (Step 22):
  The Apply button only renders if opportunity["link"] is a genuine
  http(s) URL already stored in the database — never constructed
  or guessed.
─────────────────────────────────────────────────────────────────
"""

import html
import os
import re

_TEMPLATE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "email", "opportunity_match.html")
)

with open(_TEMPLATE_PATH, encoding="utf-8") as _f:
    _TEMPLATE = _f.read()

# Matches every {{TOKEN}} placeholder in the template, e.g. {{STUDENT_NAME}}.
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _safe(value) -> str:
    """Escape any dynamic value before it goes into HTML."""
    if value is None:
        return ""
    return html.escape(str(value))


def _valid_http_url(url) -> str | None:
    """Only genuine http(s) URLs pass through. Never fabricates one."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return None


def _skill_list_html(skills: list, matched: bool) -> str:
    icon = "✓" if matched else "○"
    color = "#16a34a" if matched else "#9ca3af"
    if not skills:
        return '<p style="margin:0;color:#9ca3af;font-size:13px;">None</p>'
    items = "".join(
        f'<li style="margin:0 0 4px 0;color:{color};font-size:13px;list-style:none;">{icon} {_safe(s)}</li>'
        for s in skills
    )
    return f'<ul style="margin:0;padding:0;">{items}</ul>'


def _detail_row(label: str, value) -> str:
    """Builds one optional detail row — omitted entirely if value is falsy,
    so nothing invented ever appears (e.g. no fabricated stipend row)."""
    if not value:
        return ""
    return (
        f'<tr><td style="padding:3px 0;color:#6b7280;font-size:12px;">{_safe(label)}</td>'
        f'<td style="padding:3px 0;color:#111827;font-size:12px;font-weight:bold;text-align:right;">{_safe(value)}</td></tr>'
    )


def generate_opportunity_email(
    student_name: str,
    opportunity: dict,
    match_result: dict,
    frontend_url: str = "",
) -> tuple[str, str]:
    """
    Pure function — renders the email, sends nothing.

    student_name: the recipient's display name.
    opportunity:  dict shape from OpportunityTable.to_dict().
    match_result: dict shape from match_engine.evaluate_match()
                  (needs "score", "matched_skills", "missing_skills").
    frontend_url: optional; used only for a generic "View in Dashboard"
                  button pointing at the app's own root — never used
                  to build a fake per-opportunity URL.

    Returns (subject, html_body).
    """
    score = match_result.get("score", 0)
    matched_skills = match_result.get("matched_skills") or []
    missing_skills = match_result.get("missing_skills") or []

    apply_url = _valid_http_url(opportunity.get("link"))
    view_url = _valid_http_url(frontend_url)

    apply_button = ""
    if apply_url:
        apply_button = (
            f'<a href="{_safe(apply_url)}" target="_blank" '
            f'style="display:inline-block;background-color:#0A66C2;color:#ffffff;text-decoration:none;'
            f'padding:12px 26px;border-radius:6px;font-weight:bold;font-size:14px;">Apply Now</a>'
        )

    view_button = ""
    if view_url:
        spacer = "&nbsp;&nbsp;" if apply_button else ""
        view_button = (
            f'{spacer}<a href="{_safe(view_url)}" target="_blank" '
            f'style="display:inline-block;background-color:#ffffff;color:#0A66C2;text-decoration:none;'
            f'padding:11px 25px;border-radius:6px;font-weight:bold;font-size:14px;'
            f'border:1.5px solid #0A66C2;">View in Dashboard</a>'
        )

    description = opportunity.get("description") or ""
    if len(description) > 240:
        description = description[:240].rstrip() + "..."

    opp_type_raw = opportunity.get("type") or "opportunity"
    subject = f"{score}% Match — {opportunity.get('title') or 'New Opportunity'} at {opportunity.get('organization') or ''}"

    values = {
        "STUDENT_NAME":         _safe(student_name or "there"),
        "ORGANIZATION":         _safe(opportunity.get("organization")),
        "OPPORTUNITY_TITLE":    _safe(opportunity.get("title")),
        "OPPORTUNITY_TYPE":     _safe(opp_type_raw.title()),
        "MATCH_SCORE":          _safe(score),
        "MATCHED_SKILLS_HTML":  _skill_list_html(matched_skills, True),
        "MISSING_SKILLS_HTML":  _skill_list_html(missing_skills, False),
        "DESCRIPTION":          _safe(description),
        "LOCATION_ROW":         _detail_row("Location", opportunity.get("location")),
        "DEADLINE_ROW":         _detail_row("Deadline", opportunity.get("deadline")),
        "STIPEND_ROW":          _detail_row("Stipend", opportunity.get("stipend")),
        "APPLY_BUTTON":         apply_button,
        "VIEW_BUTTON":          view_button,
    }

    # Single pass over the ORIGINAL template, not the accumulating result —
    # unlike chained .replace() calls, this never re-scans a value we just
    # inserted. Without this, an untrusted scraped title/description that
    # happens to contain literal text like "{{APPLY_BUTTON}}" would get
    # matched and overwritten by a later .replace() call, letting external
    # data corrupt the email's structure. Unrecognized placeholders (e.g. a
    # template edited without a matching code change) are left untouched
    # rather than silently dropped or raising.
    html_body = _PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), _TEMPLATE)

    return subject, html_body
