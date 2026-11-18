import html
import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, Optional

from backend.config.settings import settings

logger = logging.getLogger(__name__)

PLACEHOLDER_EMAILS = {"", "your_email@gmail.com"}
PLACEHOLDER_PASSWORDS = {"", "your_16_char_google_app_password"}


def send_booking_confirmation_email(
    booking_reference: str,
    patient_name: str,
    department_id: str,
    department_name: str,
    provider_name: str,
    date: str,
    start_time: str,
    end_time: str,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    sender = (settings.GMAIL_SENDER_EMAIL or "").strip()
    app_password = (settings.GMAIL_APP_PASSWORD or "").strip()
    recipient = (settings.OPERATOR_NOTIFICATION_EMAIL or "").strip() or "demo@hospital.org"

    safe_ref = html.escape(booking_reference)
    safe_patient = html.escape(patient_name)
    safe_dept = html.escape(f"{department_name} ({department_id})")
    safe_provider = html.escape(provider_name)
    safe_when = html.escape(f"{date} | {start_time} - {end_time}")
    safe_run_id = html.escape(run_id or "N/A")

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #0b1120; color: #e2e8f0; padding: 24px;">
        <div style="max-width: 600px; margin: 0 auto; background: #111827; border: 1px solid #1e293b; border-radius: 12px; padding: 24px;">
          <h2 style="color: #10b981; margin-top: 0;">AegisHealth AI — Appointment Booking Confirmed</h2>
          <p>A hospital outpatient slot has been confirmed through the automated intake workflow.</p>
          <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
            <tr><td style="padding: 8px; color: #94a3b8;">Booking Reference</td><td style="padding: 8px; font-weight: bold;">{safe_ref}</td></tr>
            <tr><td style="padding: 8px; color: #94a3b8;">Patient Name</td><td style="padding: 8px;">{safe_patient}</td></tr>
            <tr><td style="padding: 8px; color: #94a3b8;">Department</td><td style="padding: 8px;">{safe_dept}</td></tr>
            <tr><td style="padding: 8px; color: #94a3b8;">Provider</td><td style="padding: 8px;">{safe_provider}</td></tr>
            <tr><td style="padding: 8px; color: #94a3b8;">Date &amp; Time</td><td style="padding: 8px;">{safe_when}</td></tr>
            <tr><td style="padding: 8px; color: #94a3b8;">Workflow Run ID</td><td style="padding: 8px;">{safe_run_id}</td></tr>
          </table>
          <p style="font-size: 12px; color: #94a3b8; border-top: 1px solid #1e293b; padding-top: 12px;">
            <strong>Privacy Notice:</strong> For patient privacy, no clinical diagnosis or symptom details are transmitted in this booking notification.
          </p>
        </div>
      </body>
    </html>
    """.strip()

    if sender in PLACEHOLDER_EMAILS or app_password in PLACEHOLDER_PASSWORDS:
        logger.info(
            "Gmail credentials not configured; simulated booking email for %s to %s",
            booking_reference,
            recipient,
        )
        return {
            "email_status": "SIMULATED_NO_CREDENTIALS",
            "recipient": recipient,
            "preview": html_body,
        }

    msg = EmailMessage()
    msg["Subject"] = f"[AegisHealth AI] Appointment Confirmed — {booking_reference}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(
        f"Appointment Confirmed ({booking_reference})\n"
        f"Patient: {patient_name}\n"
        f"Department: {department_name} ({department_id})\n"
        f"Provider: {provider_name}\n"
        f"Date & Time: {date} {start_time}-{end_time}\n"
        f"Workflow Run ID: {run_id or 'N/A'}\n\n"
        "Privacy Note: No clinical diagnosis is transmitted in this email."
    )
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender, app_password)
            server.send_message(msg)
        return {
            "email_status": "SENT_TO_GMAIL",
            "recipient": recipient,
        }
    except Exception as exc:
        logger.warning("Failed to send Gmail confirmation: %s", exc)
        return {
            "email_status": "SIMULATED_NO_CREDENTIALS",
            "recipient": recipient,
            "preview": html_body,
        }