"""Best-effort email sender. Uses ZeptoMail (matches the myratekard stack) if a token
is configured, else SMTP, else logs the message and reports not-sent. Stdlib only."""
from __future__ import annotations

import json
import smtplib
import urllib.request
from email.mime.text import MIMEText

from app.core.config import settings


def _send_zeptomail(to: str, subject: str, html: str) -> bool:
    payload = {
        "from": {"address": settings.zeptomail_sender},
        "to": [{"email_address": {"address": to}}],
        "subject": subject,
        "htmlbody": html,
    }
    req = urllib.request.Request(
        settings.zeptomail_url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": settings.zeptomail_token,  # e.g. "Zoho-enczapikey <key>"
            "User-Agent": "mech_turk/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return 200 <= resp.status < 300


def _send_smtp(to: str, subject: str, html: str) -> bool:
    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(msg["From"], [to], msg.as_string())
    return True


def send_email(to: str, subject: str, html: str) -> bool:
    """Returns True if an email was actually dispatched, False otherwise."""
    try:
        if settings.zeptomail_token and settings.zeptomail_sender:
            return _send_zeptomail(to, subject, html)
        if settings.smtp_host:
            return _send_smtp(to, subject, html)
    except Exception as e:  # never let email failure break the request
        print(f"[email] send failed to {to}: {e}")
        return False
    # No provider configured — log so the link isn't lost; caller still returns it.
    print(f"[email] (not configured) would send to {to}: {subject}")
    return False


def invite_email_html(org_name: str, role: str, link: str) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:520px;margin:auto">
      <h2 style="text-transform:uppercase;letter-spacing:1px">TURK</h2>
      <p>You've been invited to join <b>{org_name}</b> as <b>{role}</b>.</p>
      <p>Click below to create your account:</p>
      <p><a href="{link}" style="background:#00b3c4;color:#06060f;padding:12px 20px;
        border-radius:6px;text-decoration:none;font-weight:bold">Create your account</a></p>
      <p style="color:#666;font-size:12px">Or paste this link:<br>{link}</p>
    </div>
    """
