"""Transactional email via SMTP (stdlib), with a log-only dev fallback.

When ``SMTP_HOST`` is unset the message is logged instead of sent, so local
development works with no mail infrastructure and password-reset links are
discoverable in the worker/API logs. Send failures are swallowed and logged —
callers (e.g. forgot-password) must not surface delivery status to the client.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("aegis.email")


def send_email(
    to: str, subject: str, body_text: str, body_html: Optional[str] = None
) -> None:
    if not settings.SMTP_HOST:
        logger.warning(
            "SMTP not configured; email NOT sent.\n"
            "  To: %s\n  Subject: %s\n  Body:\n%s",
            to,
            subject,
            body_text,
        )
        return

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_STARTTLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:  # noqa: BLE001 - delivery failures must not break the flow
        logger.exception("Failed to send email to %s", to)


def send_password_reset_email(to: str, reset_url: str) -> None:
    minutes = settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    subject = "Reset your Aegis password"
    text = (
        "We received a request to reset your Aegis password.\n\n"
        f"Reset it here (link expires in {minutes} minutes):\n{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email — your "
        "password won't change."
    )
    html = (
        f'<div style="font-family:system-ui,sans-serif;line-height:1.5;color:#111">'
        f"<h2 style=\"margin:0 0 12px\">Reset your Aegis password</h2>"
        f"<p>We received a request to reset your Aegis password.</p>"
        f'<p><a href="{reset_url}" style="display:inline-block;background:#22D3EE;'
        f'color:#07090E;font-weight:600;text-decoration:none;padding:10px 18px;'
        f'border-radius:8px">Reset password</a></p>'
        f"<p style=\"color:#667;font-size:13px\">This link expires in {minutes} "
        f"minutes. If you didn't request this, you can ignore this email.</p>"
        f"</div>"
    )
    send_email(to, subject, text, html)
