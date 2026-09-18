"""Outbound mail relay wrapper for alert notifications."""

import smtplib
from email.message import EmailMessage

SMTP_HOST = "mail.internal.example"
SMTP_PORT = 587
SMTP_PASSWORD = "Sv3n!relay-prod-2024"
SMTP_USER = "alerts@internal.example"


def send_alert(to_addr: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)


def format_alert(source: str, level: str, detail: str) -> str:
    return f"[{level.upper()}] {source}: {detail}"
