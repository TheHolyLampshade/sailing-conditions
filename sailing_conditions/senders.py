# sailing_conditions/senders.py
from __future__ import annotations
import os
import sys
import smtplib
import ssl
import socket
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable, Optional


# ------------------------------
# Slack
# ------------------------------

def post_slack(message: str) -> None:
    """
    Send a message to Slack using either:
      1) Incoming Webhook URL (SLACK_WEBHOOK_URL), or
      2) Bot token + channel (SLACK_BOT_TOKEN + SLACK_CHANNEL)

    Prints only status/warnings; does NOT echo the message to stdout.
    """
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook:
        try:
            r = requests.post(webhook, json={"text": message}, timeout=10)
            if r.status_code >= 300:
                print(f"[warn] Slack webhook failed: {r.status_code} {r.text}", file=sys.stderr)
            else:
                print("[info] Slack webhook sent.")
        except Exception as e:
            print(f"[warn] Slack webhook error: {e}", file=sys.stderr)
        return

    bot = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL")
    if bot and channel:
        try:
            r = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {bot}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={"channel": channel, "text": message},
                timeout=10,
            )
            data = r.json()
            if not data.get("ok"):
                print(f"[warn] Slack API error: {data}", file=sys.stderr)
            else:
                print("[info] Slack bot message sent.")
        except Exception as e:
            print(f"[warn] Slack bot error: {e}", file=sys.stderr)
    else:
        print("[info] No Slack credentials set; skipping Slack send.")


# ------------------------------
# Email (HTML)
# ------------------------------

def _split_addrs(val: Optional[str]) -> list[str]:
    if not val:
        return []
    # support comma or semicolon separated lists
    parts = [p.strip() for p in val.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _smtp_params() -> dict[str, Optional[str]]:
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": os.environ.get("SMTP_PORT"),
        "user": os.environ.get("SMTP_USER"),
        "pass": os.environ.get("SMTP_PASS"),
        "from": os.environ.get("EMAIL_FROM"),
        "to": os.environ.get("EMAIL_TO"),
    }


def _smtp_ready(params: dict[str, Optional[str]]) -> bool:
    required = ("host", "port", "from", "to")
    for k in required:
        if not params.get(k) or not str(params[k]).strip():
            return False
    return True


def _build_message(subject: str, html: str, text_fallback: str, sender: str, recipients: Iterable[str]) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    # plain text first, then HTML
    part_text = MIMEText(text_fallback or "", "plain", "utf-8")
    part_html = MIMEText(html or "", "html", "utf-8")
    msg.attach(part_text)
    msg.attach(part_html)
    return msg


def send_email_html(subject: str, html: str, text_fallback: str = "") -> None:
    """
    Send a rich HTML email. Uses:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM, EMAIL_TO

    Behavior:
      - If PORT == 465: implicit SSL
      - If PORT == 587: STARTTLS
      - If SMTP_USER/PASS missing, try anonymous (some relays allow it)
      - Prints status/warnings only; does NOT echo message body
    """
    params = _smtp_params()
    if not _smtp_ready(params):
        print("[warn] Email env vars not fully set; skipping email send.")
        return

    host = params["host"]
    try:
        port = int(params["port"] or "0")
    except ValueError:
        print("[warn] Invalid SMTP_PORT; skipping email send.")
        return

    sender = params["from"]
    recipients = _split_addrs(params["to"])
    if not recipients:
        print("[warn] EMAIL_TO empty; skipping email send.")
        return

    msg = _build_message(subject, html, text_fallback, sender, recipients)

    try:
        if port == 465:
            # Implicit SSL
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as s:
                _smtp_login_if_needed(s, params)
                s.sendmail(sender, recipients, msg.as_string())
        else:
            # Assume STARTTLS if 587, otherwise try plain then upgrade if supported
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.ehlo()
                try:
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                except smtplib.SMTPException:
                    # Server may not support STARTTLS; proceed without TLS
                    pass
                _smtp_login_if_needed(s, params)
                s.sendmail(sender, recipients, msg.as_string())
        print(f"[info] Email sent to {', '.join(recipients)}.")
    except (smtplib.SMTPException, socket.gaierror, TimeoutError) as e:
        print(f"[warn] SMTP error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[warn] Email send failed: {e}", file=sys.stderr)


def _smtp_login_if_needed(smtp: smtplib.SMTP, params: dict[str, Optional[str]]) -> None:
    user = params.get("user")
    pwd = params.get("pass")
    if user and pwd:
        try:
            smtp.login(user, pwd)
        except smtplib.SMTPException as e:
            print(f"[warn] SMTP login failed: {e}", file=sys.stderr)