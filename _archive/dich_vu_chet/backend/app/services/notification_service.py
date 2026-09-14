"""
Notification Service for Medical Supply Forecasting System

Sends email notifications for critical and high-severity alerts using
aiosmtplib (async SMTP). All SMTP credentials are loaded from environment
variables / settings to keep secrets out of code.
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert import Alert
from app.models.user import User

logger = logging.getLogger(__name__)


def _build_alert_email(alert: Alert, supply_name: str) -> tuple[str, str]:
    """Return (subject, html_body) for an alert notification email."""
    severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(
        alert.severity, "⚪"
    )
    subject = (
        f"{severity_emoji} [{alert.severity.upper()}] Medical Supply Alert: {supply_name}"
    )

    shortage_date_str = (
        alert.shortage_date.isoformat() if alert.shortage_date else "Unknown"
    )
    resolved_str = "Yes" if alert.is_resolved else "No"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: {'#fee2e2' if alert.severity == 'critical' else '#fef3c7'}; 
                    padding: 20px; border-radius: 8px; border-left: 5px solid 
                    {'#dc2626' if alert.severity == 'critical' else '#d97706'};">
            <h2 style="color: {'#dc2626' if alert.severity == 'critical' else '#d97706'}; margin: 0 0 16px 0;">
                {severity_emoji} Medical Supply Shortage Alert
            </h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 6px 0; font-weight: bold; width: 40%;">Supply:</td>
                    <td style="padding: 6px 0;">{supply_name}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: bold;">Severity:</td>
                    <td style="padding: 6px 0; color: {'#dc2626' if alert.severity == 'critical' else '#d97706'};">
                        <strong>{alert.severity.upper()}</strong>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: bold;">Alert Type:</td>
                    <td style="padding: 6px 0;">{alert.alert_type}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: bold;">Current Stock:</td>
                    <td style="padding: 6px 0;">{alert.current_stock if alert.current_stock is not None else 'N/A'} units</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: bold;">Required Stock:</td>
                    <td style="padding: 6px 0;">{alert.required_stock if alert.required_stock is not None else 'N/A'} units</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: bold;">Projected Shortage Date:</td>
                    <td style="padding: 6px 0;">{shortage_date_str}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: bold;">Resolved:</td>
                    <td style="padding: 6px 0;">{resolved_str}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; font-weight: bold;">Alert Created:</td>
                    <td style="padding: 6px 0;">{alert.created_at.isoformat() if alert.created_at else 'N/A'}</td>
                </tr>
            </table>
            <hr style="margin: 16px 0; border: none; border-top: 1px solid #ccc;" />
            <p style="margin: 0; color: #555;">{alert.message or 'Please review and take action to replenish this supply.'}</p>
        </div>
        <p style="color: #999; font-size: 12px; margin-top: 16px;">
            This is an automated notification from MedForecast AI. 
            Please log in to the system to take action.
        </p>
    </body>
    </html>
    """
    return subject, html_body


def _send_email_sync(
    recipients: List[str],
    subject: str,
    html_body: str,
) -> bool:
    """
    Send an email synchronously using smtplib (stdlib).

    Returns True on success, False if SMTP is not configured or delivery fails.
    """
    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_user = settings.SMTP_USER
    smtp_password = settings.SMTP_PASSWORD

    if not smtp_user or not smtp_password:
        logger.warning(
            "SMTP credentials not configured (SMTP_USER / SMTP_PASSWORD). "
            "Skipping email notification."
        )
        return False

    if not recipients:
        logger.warning("No email recipients provided. Skipping notification.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = ", ".join(recipients)

    # Plain-text fallback
    plain_text = subject  # minimal fallback
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipients, msg.as_string())
        logger.info(
            f"Email notification sent to {recipients} | subject='{subject}'"
        )
        return True
    except smtplib.SMTPAuthenticationError as exc:
        logger.error(f"SMTP authentication failed: {exc}")
        return False
    except smtplib.SMTPException as exc:
        logger.error(f"SMTP error while sending notification: {exc}")
        return False
    except OSError as exc:
        logger.error(f"Network error while sending notification: {exc}")
        return False


async def send_alert_email_async(
    recipients: List[str],
    subject: str,
    html_body: str,
) -> bool:
    """Async wrapper — runs the blocking SMTP call in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _send_email_sync, recipients, subject, html_body
    )


class NotificationService:
    """
    Sends email notifications to users when critical/high alerts are generated.

    Usage:
        service = NotificationService(db)
        await service.notify_critical_alert(alert)
    """

    def __init__(self, db: Session):
        self.db = db

    def _get_admin_emails(self) -> List[str]:
        """Return email addresses of all active Administrator users."""
        admins = (
            self.db.query(User)
            .filter(User.role == "Administrator", User.is_active == True)  # noqa: E712
            .all()
        )
        emails = [u.email for u in admins if u.email]
        if not emails:
            logger.warning("No active Administrator users found for email notification.")
        return emails

    async def notify_alert(self, alert: Alert) -> bool:
        """
        Send an email notification for an alert to all admin users.

        Only sends for 'critical' and 'high' severity by default.
        Returns True if the email was delivered, False otherwise.
        """
        if alert.severity not in ("critical", "high"):
            logger.debug(
                f"Skipping notification for alert id={alert.id} "
                f"(severity={alert.severity})"
            )
            return False

        supply_name = (
            alert.supply.name
            if alert.supply
            else f"Supply #{alert.supply_id}"
        )

        subject, html_body = _build_alert_email(alert, supply_name)
        recipients = self._get_admin_emails()

        if not recipients:
            return False

        success = await send_alert_email_async(recipients, subject, html_body)
        if success:
            logger.info(
                f"Notification sent for alert id={alert.id} "
                f"severity={alert.severity} supply='{supply_name}'"
            )
        else:
            logger.warning(
                f"Failed to send notification for alert id={alert.id}"
            )
        return success

    async def notify_critical_alerts_batch(self, alerts: List[Alert]) -> int:
        """
        Send notifications for all critical alerts in a list.

        Returns the count of successfully sent notifications.
        """
        sent_count = 0
        for alert in alerts:
            if alert.severity == "critical":
                success = await self.notify_alert(alert)
                if success:
                    sent_count += 1
        return sent_count
