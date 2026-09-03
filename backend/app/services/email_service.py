"""
backend/app/services/email_service.py — Phase 7
─────────────────────────────────────────────────────────────────
SMTP transport ONLY. Uses Python's built-in smtplib/email modules —
no new external dependency added. This file never touches HTML
template generation (see email_templates.py) and is never imported
by scrapers, matcher, or routes directly — only by
notification_service.py.

Safety:
  - SMTP_USERNAME/SMTP_PASSWORD are NEVER logged, in success or failure.
  - When EMAIL_ENABLED=false, no SMTP connection is opened at all —
    the function logs what it would have sent and returns immediately.
    This is the safe default for local development.
─────────────────────────────────────────────────────────────────
"""

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import (
    EMAIL_ENABLED,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_USE_TLS,
)

logger = logging.getLogger(__name__)


def send_email(recipient: str, subject: str, html_body: str) -> dict:
    """
    Send one HTML email via SMTP.

    Returns (never raises — callers must be able to trust this always
    returns a result dict, so a mail failure can never crash a caller):
      {"status": "sent"}
      {"status": "skipped", "reason": "EMAIL_ENABLED=false"}
      {"status": "failed",  "reason": "<safe, non-credential description>"}
    """
    if not recipient or "@" not in recipient:
        return {"status": "failed", "reason": "Invalid recipient address"}

    if not EMAIL_ENABLED:
        logger.info(f"EMAIL DISABLED — would send '{subject[:60]}' to {recipient}")
        return {"status": "skipped", "reason": "EMAIL_ENABLED=false"}

    if not (SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD and SMTP_FROM_EMAIL):
        logger.warning("Email send skipped — SMTP is not fully configured")
        return {"status": "failed", "reason": "SMTP not configured"}

    # Defense in depth: subject text ultimately comes from scraped opportunity
    # titles (untrusted). html.escape() protects the HTML body, but the
    # subject is a raw email header — strip CR/LF so nothing can inject
    # extra headers (e.g. a fake Bcc:) via a crafted title.
    subject = subject.replace("\r", " ").replace("\n", " ").strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    server = None
    try:
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.starttls(context=ssl.create_default_context())
        else:
            server = smtplib.SMTP_SSL(
                SMTP_HOST, SMTP_PORT, timeout=15, context=ssl.create_default_context()
            )

        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, [recipient], msg.as_string())

        logger.info(f"Email sent to {recipient} — subject: {subject[:60]}")
        return {"status": "sent"}

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed (credentials not logged)")
        return {"status": "failed", "reason": "SMTP authentication failed"}
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending to {recipient}: {type(e).__name__}")
        return {"status": "failed", "reason": f"SMTP error: {type(e).__name__}"}
    except (OSError, TimeoutError) as e:
        logger.error(f"Connection error sending to {recipient}: {type(e).__name__}")
        return {"status": "failed", "reason": f"Connection error: {type(e).__name__}"}
    except Exception as e:
        logger.error(f"Unexpected error sending email: {type(e).__name__}")
        return {"status": "failed", "reason": "Unexpected error"}
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass  # connection may already be closed/broken — never let cleanup raise


# ── CLI test command (Step 24) ──────────────────────────────────────
# The existing admin architecture has no admin-only role (any valid JWT
# can hit /admin/* today), so exposing a public POST /admin/test-email
# would let ANY registered user trigger arbitrary emails — not safe.
# Per the Phase 7 spec's own instruction ("if the existing admin
# architecture is not ready, provide a CLI test command instead"), this
# is a CLI-only test path, matching the existing project convention
# (see app/scrapers/nsp.py, simplifyjobs.py — both have __main__ blocks).
#
# Usage (from backend/, with venv active):
#   python -m app.services.email_service you@example.com

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.services.email_service <recipient-email>")
        sys.exit(1)

    recipient = sys.argv[1]
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    test_html = """
    <html><body style="font-family:sans-serif;padding:20px;">
      <h2>Opportunity Matcher — Test Email</h2>
      <p>If you're reading this, SMTP is configured correctly.</p>
    </body></html>
    """

    print(f"EMAIL_ENABLED = {EMAIL_ENABLED}")
    result = send_email(recipient, "Opportunity Matcher — Test Email", test_html)
    print("Result:", result)
