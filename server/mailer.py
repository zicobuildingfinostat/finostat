"""Outbound email for magic links, over stdlib smtplib.

Configured via SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / SMTP_FROM. When
nothing is configured the link is logged instead of sent -- that is how local
development and the test suite work, and it is loud enough in the logs that
nobody will mistake it for production.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger("finostat.mailer")


def configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASS"))


def _message(to: str, link: str) -> EmailMessage:
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "no-reply@finostat.com"
    msg = EmailMessage()
    msg["Subject"] = "Your Finostat sign-in link"
    msg["From"] = f"Finostat <{sender}>"
    msg["To"] = to
    msg.set_content(
        "Sign in to Finostat:\n\n"
        f"{link}\n\n"
        "This link works once and expires in 15 minutes.\n"
        "If you didn't request it, ignore this email -- nothing happens without the link.\n"
    )
    msg.add_alternative(f"""\
<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:520px;margin:0 auto;padding:28px 20px;color:#1a1338">
  <p style="font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#6d609e;margin:0 0 10px">Finostat</p>
  <h1 style="font-size:22px;margin:0 0 14px">Sign in to Finostat</h1>
  <p style="margin:0 0 22px;line-height:1.5">Click the button to sign in. The link works once and expires in 15 minutes.</p>
  <p style="margin:0 0 26px"><a href="{link}" style="display:inline-block;background:#f5c842;color:#2a1a02;text-decoration:none;font-weight:600;padding:12px 20px;border-radius:4px">Sign in →</a></p>
  <p style="font-size:12px;color:#6d609e;line-height:1.5;margin:0">If you didn't request this, ignore it — nothing happens without the link.<br>
  Or paste this into your browser: <span style="word-break:break-all">{link}</span></p>
</div>""", subtype="html")
    return msg


def send_magic_link(to: str, link: str) -> bool:
    """True if handed to an SMTP server (or logged in dev mode); False on failure."""
    if not configured():
        log.warning("SMTP not configured -- magic link for %s (DEV ONLY): %s", to, link)
        return True
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465") or 465)
    user, password = os.environ["SMTP_USER"], os.environ["SMTP_PASS"]
    msg = _message(to, link)
    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ctx)
                s.login(user, password)
                s.send_message(msg)
        log.info("magic link sent to %s", to)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.error("could not send magic link to %s: %s", to, exc)
        return False
