"""Delivery channels. Each one switches on when its secrets are set (env vars / .env)."""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from . import report
from .report import RunSummary

log = logging.getLogger(__name__)


def _env_list(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


class Telegram:
    name = "telegram"

    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_ids = _env_list("TELEGRAM_CHAT_ID")

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_ids)

    def _send(self, chat_id: str, text: str, preview: bool) -> None:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                   "link_preview_options": {"is_disabled": not preview}}
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        for attempt in range(3):
            request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    json.load(response)
                    return
            except urllib.error.HTTPError as exc:
                body = exc.read().decode(errors="replace")
                if exc.code == 429 and attempt < 2:
                    retry = json.loads(body).get("parameters", {}).get("retry_after", 5)
                    time.sleep(float(retry) + 1)
                    continue
                raise RuntimeError(f"Telegram error {exc.code}: {body[:300]}") from None

    def send_messages(self, messages: list[str], preview: bool = False) -> None:
        for chat_id in self.chat_ids:
            for message in messages:
                self._send(chat_id, message, preview)
                time.sleep(1.1)  # stay well under Telegram's per-chat rate limit

    def send_run(self, run: RunSummary, lang: str, individual_limit: int) -> None:
        label = lambda l: run.source_labels.get(l.source, l.source)  # noqa: E731
        items = [("drop", l) for l in run.drops] + [("new", l) for l in run.new]
        self.send_messages(report.chunk_lines(report.telegram_summary(run, lang)))
        if not items:
            return
        if len(items) <= individual_limit:
            # One message per property: shows a photo preview and is easy to forward.
            self.send_messages([report.telegram_listing(l, lang, label(l), kind) for kind, l in items],
                               preview=True)
        else:
            lines = [report.telegram_digest_line(l, lang, label(l)) for _, l in items]
            self.send_messages(report.chunk_lines(lines))

    def send_test(self, text: str) -> None:
        self.send_messages([text])


class Email:
    name = "email"

    def __init__(self):
        self.user = os.environ.get("SMTP_USER", "").strip()
        self.password = os.environ.get("SMTP_PASSWORD", "").strip()
        self.to = _env_list("EMAIL_TO") or ([self.user] if self.user else [])
        self.host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
        self.port = int(os.environ.get("SMTP_PORT", "465"))
        self.sender = os.environ.get("EMAIL_FROM", self.user).strip()

    @property
    def configured(self) -> bool:
        return bool(self.user and self.password and self.to)

    def _send(self, subject: str, text: str, html_body: str | None) -> None:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.sender
        message["To"] = ", ".join(self.to)
        message.attach(MIMEText(text, "plain", "utf-8"))
        if html_body:
            message.attach(MIMEText(html_body, "html", "utf-8"))
        context = ssl.create_default_context()
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=60) as smtp:
                smtp.login(self.user, self.password)
                smtp.sendmail(self.sender, self.to, message.as_string())
        else:
            with smtplib.SMTP(self.host, self.port, timeout=60) as smtp:
                smtp.starttls(context=context)
                smtp.login(self.user, self.password)
                smtp.sendmail(self.sender, self.to, message.as_string())

    def send_run(self, run: RunSummary, lang: str, individual_limit: int) -> None:
        lab = report.L(lang)
        counts = []
        if run.new:
            counts.append(lab["new_count"].format(n=len(run.new)))
        if run.drops:
            counts.append(lab["drop_count"].format(n=len(run.drops)))
        subject = f"{lab['title']} - {' · '.join(counts) if counts else lab['nothing_new']}"
        self._send(subject, report.plain_text(run, lang), report.render_html(run, lang, include_all=False))

    def send_test(self, text: str) -> None:
        self._send("Real-estate alerts: test", text, None)


class WhatsApp:
    """Free WhatsApp messages to your own number via CallMeBot (https://www.callmebot.com)."""

    name = "whatsapp"

    def __init__(self):
        self.phone = os.environ.get("WHATSAPP_PHONE", "").strip()
        self.apikey = os.environ.get("CALLMEBOT_APIKEY", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.phone and self.apikey)

    def _send(self, text: str) -> None:
        query = urllib.parse.urlencode({"phone": self.phone, "text": text, "apikey": self.apikey})
        with urllib.request.urlopen(f"https://api.callmebot.com/whatsapp.php?{query}", timeout=60) as resp:
            body = resp.read().decode(errors="replace")
        if "error" in body.lower() and "queued" not in body.lower():
            raise RuntimeError(f"CallMeBot: {body[:200]}")

    def send_run(self, run: RunSummary, lang: str, individual_limit: int) -> None:
        for part in report.chunk_lines(report.plain_text(run, lang).split("\n\n"), limit=1500, sep="\n\n"):
            self._send(part)
            time.sleep(3)

    def send_test(self, text: str) -> None:
        self._send(text)


def channels() -> list:
    return [c for c in (Telegram(), Email(), WhatsApp()) if c.configured]


def deliver(run: RunSummary, lang: str, individual_limit: int) -> bool:
    """Send to every configured channel. True if at least one succeeded (or none configured)."""
    active = channels()
    if not active:
        log.warning("No notification channel configured - results are only in the report file. "
                    "Set TELEGRAM_* / SMTP_* / WHATSAPP_* (see README).")
        return True
    delivered = False
    for channel in active:
        try:
            channel.send_run(run, lang, individual_limit)
            log.info("Sent to %s", channel.name)
            delivered = True
        except Exception as exc:
            log.error("Sending to %s failed: %s", channel.name, exc)
    return delivered
