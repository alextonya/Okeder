"""
Service email — notifications automatiques (B).
Utilise SMTP async via aiosmtplib.
Fallback silencieux si SMTP non configuré.
"""
import asyncio
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


async def send_proposal_email(
    to_email: str,
    participant_name: str,
    event_title: str,
    proposal_summary: str,
    result_url: str,
) -> bool:
    """Envoie l'email de notification de proposal."""
    if not settings.smtp_user or not settings.smtp_password:
        logger.info("SMTP non configuré — email skipped pour %s", to_email)
        return False

    subject = f"🎯 Your group outing is planned! — {event_title}"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,sans-serif;background:#0f172a;color:#f1f5f9;padding:24px;margin:0">
  <div style="max-width:480px;margin:0 auto">
    <h1 style="color:#6366f1;font-size:24px;margin-bottom:8px">🎯 Okeder</h1>
    <p style="color:#94a3b8;margin-bottom:24px">Hi {participant_name},</p>

    <div style="background:#1e293b;border-radius:16px;padding:20px;margin-bottom:20px">
      <p style="font-size:18px;font-weight:700;margin-bottom:16px">{event_title}</p>
      <pre style="font-family:inherit;font-size:14px;white-space:pre-wrap;color:#e2e8f0;margin:0">{proposal_summary}</pre>
    </div>

    <a href="{result_url}"
       style="display:block;background:#6366f1;color:white;text-decoration:none;
              text-align:center;padding:14px 20px;border-radius:12px;font-weight:600;
              font-size:16px">
      View full proposal →
    </a>

    <p style="color:#475569;font-size:12px;margin-top:24px;text-align:center">
      Sent by Okeder · <a href="{result_url}" style="color:#6366f1">okeder.app</a>
    </p>
  </div>
</body>
</html>"""

    text = f"Hi {participant_name},\n\nYour group outing is planned!\n\n{proposal_summary}\n\nView full proposal: {result_url}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.email_from
    msg["To"]      = to_email
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    def _send_sync():
        import smtplib
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_from, to_email, msg.as_string())

    try:
        await asyncio.to_thread(_send_sync)
        logger.info("Email sent to %s", to_email)
        return True
    except Exception as e:
        logger.warning("Email failed to %s: %s", to_email, e)
        return False
